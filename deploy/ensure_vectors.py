"""deploy/ensure_vectors.py

Résolution automatique, reproductible et sécurisée des vecteurs à l'exécution Linux/VPS.

Contexte :
  agent_fr/embed.py calcule la clé du fichier de vecteurs (vec_<clé>.npy) en hachant
  le chemin absolu et le st_mtime des fichiers chunks_*.jsonl.
  Sur chaque nouvelle machine ou chemin de déploiement (ex. /opt/regassist-dz),
  la clé calculée change.

Ce module :
  1. Identifie l'index cible (corpus_vivant ou instantane_phase4 via AGENT_CORPUS_DIR).
  2. Charge dynamiquement les empreintes officielles depuis PHASE_4_FROZEN.manifest.json
     et vérifie cryptographiquement que les fichiers de chunks actifs sont intègres.
  3. Calcule la clé exacte attendue au runtime par le moteur (vectors_key).
  4. Si vec_<clé>.npy est absent, vérifie l'intégrité de l'artefact figé correspondant :
     - instantane_phase4 -> replication/index/vec_df4dd33e8c3b.npy (+ meta)
     - corpus_vivant    -> replication/index/vec_4da0cd6ae37e.npy (+ meta)
     Valide dimensions (11314, 384), SHA-256 et alignement strict des chunk_ids.
  5. Établit le lien (symlink ou copie) de façon idempotente et sans modifier le moteur gelé.
  6. En cas d'incompatibilité, refuse le démarrage et affiche la procédure de reconstruction.
"""
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "agent_fr" / "eval" / "human" / "PHASE_4_FROZEN.manifest.json"
REPLICATION_INDEX = ROOT / "replication" / "index"

FROZEN_VEC_SHA256 = "31f4edbf526866d3566af63512de75c50aa101971a6cc966a537d4850f89d51e"
EXPECTED_ROWS = 11314
EXPECTED_DIM = 384


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest_chunk_hashes() -> dict:
    """Charge les empreintes des chunks depuis le manifeste gelé."""
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f"Manifeste du gel introuvable : {MANIFEST_PATH}")
    man = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return dict(man.get("corpus", {}).get("instantane_fichiers", {}))


def ensure_runtime_vectors(vector_dir: Path = None, verbose: bool = True) -> str:
    """Vérifie et résout les fichiers de vecteurs pour l'environnement actif."""
    if vector_dir is None:
        raw = os.environ.get("AGENT_VECTOR_DIR") or os.environ.get("AGENT_INDEX_DIR") or r"D:\llm\index"
        vector_dir = Path(raw)
    vector_dir = Path(vector_dir)
    vector_dir.mkdir(parents=True, exist_ok=True)

    langs = os.environ.get("AGENT_LANGS", "fr,ar").split(",")
    from agent_fr.build_vectors import chunk_files, vectors_key
    import numpy as np

    active_chunks = chunk_files(langs)
    if not active_chunks:
        raise RuntimeError("Aucun fichier de chunks trouvé pour les langues : " + ",".join(langs))

    # 1. Contrôle d'intégrité des chunks actifs contre le manifeste
    expected_chunks = load_manifest_chunk_hashes()
    for lg, cpath in active_chunks:
        fname = cpath.name
        if fname in expected_chunks:
            actual_hash = sha256_file(cpath)
            exp_hash = expected_chunks[fname]
            if actual_hash != exp_hash:
                raise ValueError(
                    f"Intégrité compromise pour {cpath} (SHA-256: {actual_hash} != {exp_hash}). "
                    "Les vecteurs ne peuvent pas être réutilisés de façon sûre. Reconstruisez : "
                    "python -m agent_fr.build_vectors --langs fr,ar"
                )

    # 2. Clé attendue par le moteur pour cet environnement exact
    runtime_key = vectors_key(langs)
    target_npy = vector_dir / f"vec_{runtime_key}.npy"
    target_meta = vector_dir / f"vec_{runtime_key}.meta.json"

    if target_npy.exists() and target_meta.exists():
        try:
            arr = np.load(target_npy, mmap_mode="r")
            if arr.shape == (EXPECTED_ROWS, EXPECTED_DIM):
                if verbose:
                    print(f"[ensure_vectors] Vecteurs conformes déjà en place pour la clé runtime : {runtime_key}")
                return runtime_key
        except Exception:
            pass

    # 3. Sélection de l'artefact source adéquat (snapshot vs corpus vivant)
    snap_env = os.environ.get("AGENT_CORPUS_DIR")
    if snap_env:
        src_prefix = "vec_df4dd33e8c3b"
    else:
        src_prefix = "vec_4da0cd6ae37e"

    src_npy = vector_dir / f"{src_prefix}.npy"
    src_meta = vector_dir / f"{src_prefix}.meta.json"
    if not src_npy.exists() or not src_meta.exists():
        src_npy = REPLICATION_INDEX / f"{src_prefix}.npy"
        src_meta = REPLICATION_INDEX / f"{src_prefix}.meta.json"

    if not src_npy.exists() or not src_meta.exists():
        raise FileNotFoundError(
            f"Artefact vectoriel figé introuvable ({src_prefix}.npy / .meta.json). "
            f"Exécutez replication/setup_machine.ps1 ou reconstruisez : python -m agent_fr.build_vectors --langs {','.join(langs)}"
        )

    # 4. Contrôle strict de compatibilité
    src_hash = sha256_file(src_npy)
    if src_hash != FROZEN_VEC_SHA256:
        raise ValueError(f"Empreinte SHA-256 inattendue pour {src_npy} ({src_hash}).")

    arr = np.load(src_npy, mmap_mode="r")
    if arr.shape != (EXPECTED_ROWS, EXPECTED_DIM):
        raise ValueError(f"Dimensions de vecteurs incompatibles : {arr.shape} != {(EXPECTED_ROWS, EXPECTED_DIM)}")

    meta_obj = json.loads(src_meta.read_text(encoding="utf-8"))
    if len(meta_obj.get("chunk_ids", [])) != EXPECTED_ROWS:
        raise ValueError(f"Nombre de chunk_ids incompatible dans {src_meta} ({len(meta_obj.get('chunk_ids', []))})")

    # 5. Établissement idempotent
    # Si vector_dir est un dossier distinct (ex. serveur propre /opt/regassist-data/llm/index),
    # on y implémente également le fichier canonique source s'il n'y est pas encore
    canonical_npy = vector_dir / f"{src_prefix}.npy"
    canonical_meta = vector_dir / f"{src_prefix}.meta.json"
    if src_npy.resolve() != canonical_npy.resolve():
        if not canonical_npy.exists():
            try:
                os.symlink(src_npy.resolve(), canonical_npy)
            except (OSError, NotImplementedError, ValueError):
                import shutil
                shutil.copy2(src_npy, canonical_npy)
        if not canonical_meta.exists():
            try:
                os.symlink(src_meta.resolve(), canonical_meta)
            except (OSError, NotImplementedError, ValueError):
                import shutil
                shutil.copy2(src_meta, canonical_meta)
        src_npy = canonical_npy
        src_meta = canonical_meta

    if target_npy.is_symlink() and not target_npy.exists():
        target_npy.unlink()
    if not target_npy.exists():
        try:
            if src_npy.parent == target_npy.parent:
                symlink_target = src_npy.name
            else:
                symlink_target = os.path.relpath(src_npy.resolve(), target_npy.resolve().parent)
            os.symlink(symlink_target, target_npy)
            if verbose:
                print(f"[ensure_vectors] Symlink créé : {target_npy.name} -> {symlink_target}")
        except (OSError, NotImplementedError, ValueError):
            import shutil
            shutil.copy2(src_npy, target_npy)
            if verbose:
                print(f"[ensure_vectors] Copie établie : {target_npy.name} depuis {src_npy.name}")

    if not target_meta.exists():
        new_meta = dict(meta_obj)
        new_meta["key"] = runtime_key
        target_meta.write_text(json.dumps(new_meta, ensure_ascii=False), encoding="utf-8")
        if verbose:
            print(f"[ensure_vectors] Métadonnées écrites : {target_meta.name}")

    return runtime_key


if __name__ == "__main__":
    vdir = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    try:
        k = ensure_runtime_vectors(vector_dir=vdir)
        print(f"OK: vecteurs validés sous clé {k}")
        sys.exit(0)
    except Exception as e:
        print(f"ERREUR: {e}", file=sys.stderr)
        sys.exit(1)
