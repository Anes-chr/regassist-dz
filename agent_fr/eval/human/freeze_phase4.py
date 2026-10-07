"""PHASE_4_FROZEN — gel technique du système avant la validation juridique (phase 5).

`create`  écrit UNE fois le manifeste complet (versions, configuration, modèles, embeddings, reranker, corpus, index, TEST v1, règles, code, interfaces, résultats) et le marqueur `PHASE_4_FROZEN` ;
          il refuse de réécrire un manifeste existant (un gel ne se refait pas : on en ouvre un nouveau sous un autre nom, avec décision écrite).
`verify`  recalcule toutes les empreintes et compare ; code de sortie 1 si une empreinte « stricte » diffère ou si un fichier de code non listé est apparu (modification du moteur).
`repro`   vérifications de REPRODUCTIBILITÉ sans rien modifier : empreintes, ré-encodage complet des vecteurs, reconstruction du corpus dans un dossier temporaire, retrieval DEV rejoué, génération LLM rejouée
          sans cache sur un petit échantillon. TEST v1 n'est jamais ré-exécuté.
Statut conservé : NO-GO PROVISOIRE (validation humaine absente, TEST v2 absent).
Usage : python -m agent_fr.eval.human.freeze_phase4 create | verify [--json] | repro [--skip-llm]"""
import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from importlib import metadata
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
MANIFEST = HERE / "PHASE_4_FROZEN.manifest.json"
MARKER = ROOT / "PHASE_4_FROZEN"
RESULTS = ROOT / "agent_fr" / "eval" / "results"
SNAP = Path("D:/llm/snapshots/corpus_phase4")
STATUT = "NO-GO PROVISOIRE"
RAISON = ["validation humaine absente", "TEST v2 absent"]
CODE_GLOBS = ["agent_fr/*.py", "agent_fr/eval/*.py", "agent_fr/eval/human/*.py", "boa_pipeline/*.py", "tests/*.py", "llm_local/*.ps1", "llm_local/*.py"]
CODE_FILES = ["boa_pipeline/twin_overrides.json"]
RULE_FILES = ["agent_fr/eval/human/bench.py", "agent_fr/eval/human/score.py", "agent_fr/eval/human/run_bench.py", "agent_fr/eval/human/decision_criteria.md", "agent_fr/eval/human/decision_criteria.md.sha256",
              "agent_fr/eval/human/frozen_rules_manifest.json", "agent_fr/eval/human/frozen_test_v1.sha256.json"]
BENCH_FILES = ["agent_fr/eval/human/benchmark_v1_draft.jsonl", "agent_fr/eval/human/benchmark_v1_draft.jsonl.sha256", "agent_fr/eval/human/benchmark_dev_phase4.jsonl", "agent_fr/eval/human/benchmark_dev_phase4.remap.json"]
RESULT_GLOBS = ["human_bench_dev_phase4.json", "human_score_dev_phase4.json", "regression_phase4_*.json", "regression_phase3_*.json", "human_bench_dev_final2.json", "human_score_dev_final2.json",
                "human_bench_test_final.json", "human_score_test_final.json", "FROZEN_SHA256.txt", "ocr_bench_scores.json", "ocr_bench/*.json", "ocr_alert_audit*.json", "corpus_check_phase4.*",
                "twins_phase4.csv", "perf_phase3.json"]
INFO_DOCS = ["docs/RETRIEVAL_PHASE2.md", "docs/RETRIEVAL_PHASE3.md", "docs/RETRIEVAL_PHASE4.md", "docs/tables_phase4.md", "docs/HUMAN_REVIEW.md", "docs/HUMAN_REVIEW_QUICKSTART.md",
             "docs/NOTE_AU_JURISTE.md", "docs/CAS_CRITIQUES_A_EXAMINER.md", "docs/ARBITRAGE_JUMEAUX_FR_AR.md"]
PACKAGES = ["numpy", "onnxruntime", "tokenizers", "requests", "PyMuPDF", "pytesseract", "Pillow", "psutil", "truststore", "Flask", "python-docx", "openpyxl"]


def sha(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(p) -> str:
    try:
        return str(Path(p).resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(p).replace("\\", "/")


def hashes(paths) -> dict:
    return {rel(p): {"sha256": sha(p), "bytes": Path(p).stat().st_size} for p in sorted({Path(x) for x in paths}) if Path(p).is_file()}


def glob_all(globs, base=ROOT):
    return [p for g in globs for p in sorted(Path(base).glob(g)) if p.is_file() and "__pycache__" not in p.parts]


def run(cmd, **kw):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace", **kw)
        return (r.stdout + "\n" + r.stderr).strip()                                  # llama-server écrit sa version sur stderr
    except Exception as e:                                                       # noqa: BLE001
        return f"indisponible : {type(e).__name__}"


# ----------------------------------------------------------------------------------- collecte
def versions() -> dict:
    pk = {}
    for n in PACKAGES:
        try:
            pk[n] = metadata.version(n)
        except metadata.PackageNotFoundError:
            pk[n] = None
    tess = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    llama = Path("D:/llm/llama.cpp") / (Path("D:/llm/llama.cpp/CURRENT_TAG.txt").read_text().strip()) / "llama-server.exe"
    return {"python": sys.version.split()[0], "plateforme": platform.platform(), "paquets": pk,
            "tesseract": (run([str(tess), "--version"]).splitlines() or ["?"])[0], "llama_cpp_tag": Path("D:/llm/llama.cpp/CURRENT_TAG.txt").read_text().strip(),
            "llama_server": (run([str(llama), "--version"]) or "").splitlines()[:2]}


def configuration() -> dict:
    for k in ("AGENT_CORPUS_DIR", "AGENT_LLM", "AGENT_RETRIEVER"):
        os.environ.pop(k, None)                                                  # constantes « par défaut » : l'environnement de l'opérateur ne doit pas fausser le gel
    from agent_fr import answer, embed, llm_backends, pipelines, rerank, retrieve2
    from boa_pipeline import config as C
    c2 = {k: getattr(retrieve2, k) for k in ("TOPN", "COS_MIN", "COS_HIGH", "RR_MIN", "MIN_COV", "MIN_RATIO", "SUPERSEDED_FACTOR", "FUTURE_FACTOR", "ABROGATED_FACTOR", "VERSION_FACTOR",
                                             "SERIES_MATCH", "SERIES_OTHER", "PAIR_COS_WHOLE") if hasattr(retrieve2, k)}
    for k in dir(retrieve2):
        if k.startswith("W_") or k in ("RRF_K", "K_RRF", "RERANK_TOP", "RERANK_N"):
            c2[k] = getattr(retrieve2, k)
    start = (ROOT / "llm_local" / "start_server.ps1").read_text(encoding="utf-8", errors="replace")
    args = next((l.strip() for l in start.splitlines() if l.strip().startswith("$srvArgs")), "")
    cfg = (ROOT / "llm_local" / "config.ps1").read_text(encoding="utf-8", errors="replace")
    return {"retrieval": c2, "retriever_par_defaut": "AGENT_RETRIEVER=auto -> hybrid_rerank (repli legacy automatique ; AGENT_RETRIEVER=legacy = retour arrière)", "moteurs_enregistres": sorted(pipelines.PIPELINES) if hasattr(pipelines, "PIPELINES") else None,
            "embeddings": {"modele": "intfloat/multilingual-e5-small (ONNX, CPU)", "dossier": str(embed.MODEL_DIR)}, "reranker": {"modele": "mmarco-mMiniLMv2-L12-H384 int8 (ONNX)", "fichier": rerank.MODEL},
            "llm": {"fournisseur_par_defaut": llm_backends.provider(), "profils": llm_backends.PROFILE, "schema_sortie": llm_backends.SCHEMA, "modele": "qwen3-4b-instruct-2507-q4_k_m.gguf (llama.cpp, 127.0.0.1:8187)",
                    "serveur_arguments": args, "serveur_config": cfg},
            "prompt_systeme_sha256": hashlib.sha256(answer.SYSTEM.encode("utf-8")).hexdigest(), "refus_phrase": answer.NOT_FOUND,
            "pipeline_corpus": {k: getattr(C, k) for k in ("CHUNK_MAX_CHARS", "OCR_DPI", "OCR_DPI_AR", "OCR_MIN_CHARS_PER_PAGE", "OCR_LOW_CONF")},
            "ocr": {"moteur_actuel": "Tesseract 5.5, modèle ara (rapide, installé) + fra, 400 dpi pour l'arabe, repli OCR des couches texte corrompues", "candidat_experimental": "D:/llm/tessdata_best (ara best) : NON DÉPLOYÉ",
                    "OCR_UNCERTAIN": "actif (boa_pipeline/ocr_check.py -> chunks -> agent_fr/answer.py ocr_warnings)"}}


def models() -> dict:
    files = [Path("D:/llm/models/qwen3-4b-instruct-2507-q4_k_m.gguf"), Path("D:/llm/llama.cpp") / Path("D:/llm/llama.cpp/CURRENT_TAG.txt").read_text().strip() / "llama-server.exe"]
    files += sorted(Path("D:/llm/models/embeddings").rglob("*.onnx")) + sorted(Path("D:/llm/models/embeddings").rglob("tokenizer.json"))
    files += sorted(Path("D:/llm/models/rerankers").rglob("*.onnx")) + sorted(Path("D:/llm/models/rerankers").rglob("tokenizer.json"))
    files += [Path(r"C:\Program Files\Tesseract-OCR\tessdata\ara.traineddata"), Path(r"C:\Program Files\Tesseract-OCR\tessdata\fra.traineddata"), Path("D:/llm/tessdata_best/ara.traineddata")]
    return {str(p).replace("\\", "/"): {"sha256": sha(p), "bytes": p.stat().st_size} for p in files if p.exists()}


def vec_files() -> dict:
    """Fichiers de vecteurs du corpus figé et du corpus vivant (clé = chemin + taille + date du fichier de chunks : elle change si on copie le corpus ; l'empreinte du .npy est la référence)."""
    from agent_fr.build_vectors import vectors_key
    out = {}
    for tag, env in (("instantane_phase4", str(SNAP)), ("corpus_vivant", None)):
        if env:
            os.environ["AGENT_CORPUS_DIR"] = env
        else:
            os.environ.pop("AGENT_CORPUS_DIR", None)
        k = vectors_key(["fr", "ar"])
        for suffix in (".npy", ".meta.json"):
            p = Path("D:/llm/index") / f"vec_{k}{suffix}"
            if p.exists():
                out[f"{tag}:{p.name}"] = {"sha256": sha(p), "bytes": p.stat().st_size}
    os.environ.pop("AGENT_CORPUS_DIR", None)
    return out


def corpus_block() -> dict:
    snap = {p.name: sha(p) for p in sorted(SNAP.glob("*")) if p.is_file()}
    live = {}
    pairs = [("corpus/chunks/chunks_fr.jsonl", "chunks_fr.jsonl"), ("corpus/chunks/chunks_ar.jsonl", "chunks_ar.jsonl"), ("corpus/chunks/chunks_und.jsonl", "chunks_und.jsonl"),
             ("corpus/metadata/documents_fr.json", "documents_fr.json"), ("corpus/metadata/documents_ar.json", "documents_ar.json"), ("corpus/metadata/documents_und.json", "documents_und.json"),
             ("corpus/metadata/legal_status.json", "legal_status.json")]
    for src, name in pairs:
        live[src] = {"sha256": sha(ROOT / src), "identique_a_l_instantane": sha(ROOT / src) == snap.get(name)}
    docs = []
    for lg in ("fr", "ar", "und"):
        d = json.loads((SNAP / f"documents_{lg}.json").read_text(encoding="utf-8"))
        docs += d if isinstance(d, list) else list(d.values())
    raw = {}
    for d in docs:
        raw[d["raw_path"]] = d["file_hash"]
    bad = [p for p, h in raw.items() if not (ROOT / "corpus" / p).exists() or sha(ROOT / "corpus" / p) != h]
    state = hashes(ROOT / "state" / n for n in ("candidates.json", "state.json", "media_index.json", "pages.json"))
    cache = sorted((ROOT / "state" / "extract_cache").glob("*.json"))
    agg = hashlib.sha256("\n".join(f"{p.name} {sha(p)}" for p in cache).encode()).hexdigest()
    return {"instantane": rel(SNAP), "instantane_fichiers": snap, "corpus_vivant": live, "documents": len(docs),
            "fichiers_sources_raw": {"n": len(raw), "empreintes_differentes_de_file_hash": bad, "agregat_sha256": hashlib.sha256("\n".join(f"{p} {h}" for p, h in sorted(raw.items())).encode()).hexdigest()},
            "state": state, "state_extract_cache": {"fichiers": len(cache), "agregat_sha256": agg}}


def collect() -> dict:
    t0 = time.time()
    code = hashes(glob_all(CODE_GLOBS) + [ROOT / f for f in CODE_FILES])
    man = {"label": "PHASE_4_FROZEN", "cree_le": time.strftime("%Y-%m-%dT%H:%M:%S"), "statut_decision": STATUT, "raisons_du_statut": RAISON,
           "consigne": "gel de validation : ne plus modifier moteur, embeddings, reranker, poids de fusion, chunking, ranking, logique temporelle, seuils, notation, TEST v1 ; tessdata_best non déployé ; OCR_UNCERTAIN actif",
           "versions": versions(), "configuration": configuration(), "modeles": models(), "corpus": corpus_block(), "index": {"vecteurs": vec_files()},
           "test_v1": hashes(ROOT / f for f in json.loads((HERE / "frozen_test_v1.sha256.json").read_text(encoding="utf-8"))),
           "regles": hashes(ROOT / f for f in RULE_FILES), "benchmark": hashes(ROOT / f for f in BENCH_FILES), "code": code,
           "interfaces_et_fiches": hashes(glob_all(["agent_fr/eval/human/review/*"])), "resultats_phase4": hashes(glob_all(RESULT_GLOBS, RESULTS)),
           "informatif_non_strict": {"documents": hashes(ROOT / f for f in INFO_DOCS), "cache_vecteurs": hashes([Path("D:/llm/index/vec_cache_e5small.npz")])}}
    unc = 0
    for lg in ("fr", "ar", "und"):
        with open(SNAP / f"chunks_{lg}.jsonl", encoding="utf-8") as f:
            unc += sum(1 for l in f if '"ocr_uncertain": true' in l)
    man["ocr_uncertain_chunks_dans_l_instantane"] = unc
    man["duree_collecte_s"] = round(time.time() - t0, 1)
    return man


# ----------------------------------------------------------------------------------- vérification
def compare(frozen: dict, now: dict) -> dict:
    """Compare les groupes « stricts » ; renvoie {groupe: [écarts]}."""
    diffs = {}

    def cmp_files(group, a, b, ignore_new=False):
        d = [f"modifié : {k}" for k, v in a.items() if k in b and v["sha256"] != b[k]["sha256"]] + [f"absent : {k}" for k in a if k not in b]
        if not ignore_new:
            d += [f"non listé (nouveau fichier) : {k}" for k in b if k not in a]
        if d:
            diffs[group] = d
    for g in ("code", "test_v1", "regles", "benchmark", "interfaces_et_fiches", "resultats_phase4", "modeles"):
        cmp_files(g, frozen[g], now[g], ignore_new=(g in ("modeles",)))
    cmp_files("index.vecteurs", frozen["index"]["vecteurs"], now["index"]["vecteurs"])
    d = [f"modifié : {k}" for k, v in frozen["corpus"]["instantane_fichiers"].items() if now["corpus"]["instantane_fichiers"].get(k) != v]
    d += [f"corpus vivant ≠ instantané : {k}" for k, v in now["corpus"]["corpus_vivant"].items() if not v["identique_a_l_instantane"]]
    d += [f"corpus vivant modifié : {k}" for k, v in frozen["corpus"]["corpus_vivant"].items() if now["corpus"]["corpus_vivant"][k]["sha256"] != v["sha256"]]
    if now["corpus"]["fichiers_sources_raw"]["empreintes_differentes_de_file_hash"]:
        d.append("fichiers sources raw modifiés : " + ", ".join(now["corpus"]["fichiers_sources_raw"]["empreintes_differentes_de_file_hash"][:5]))
    if now["corpus"]["fichiers_sources_raw"]["agregat_sha256"] != frozen["corpus"]["fichiers_sources_raw"]["agregat_sha256"]:
        d.append("ensemble des fichiers sources raw différent")
    for k in ("state",):
        d += [f"modifié : {x}" for x, v in frozen["corpus"][k].items() if now["corpus"][k].get(x, {}).get("sha256") != v["sha256"]]
    if now["corpus"]["state_extract_cache"]["agregat_sha256"] != frozen["corpus"]["state_extract_cache"]["agregat_sha256"]:
        d.append("cache d'extraction (OCR) modifié")
    if d:
        diffs["corpus"] = d
    cfg = [k for k in ("retrieval", "embeddings", "reranker", "llm", "prompt_systeme_sha256", "refus_phrase", "pipeline_corpus", "ocr", "retriever_par_defaut", "moteurs_enregistres")
           if frozen["configuration"].get(k) != now["configuration"].get(k)]
    if cfg:
        diffs["configuration"] = [f"modifiée : {k}" for k in cfg]
    ver = [k for k in ("python", "paquets", "tesseract", "llama_cpp_tag", "llama_server") if frozen["versions"].get(k) != now["versions"].get(k)]
    if ver:
        diffs["versions"] = [f"modifiée : {k}" for k in ver]
    if frozen["ocr_uncertain_chunks_dans_l_instantane"] != now["ocr_uncertain_chunks_dans_l_instantane"]:
        diffs["ocr_uncertain"] = [f"{frozen['ocr_uncertain_chunks_dans_l_instantane']} -> {now['ocr_uncertain_chunks_dans_l_instantane']} chunks"]
    return diffs


def verify(as_json=False) -> int:
    frozen = json.loads(MANIFEST.read_text(encoding="utf-8"))
    now = collect()
    diffs = compare(frozen, now)
    info = [f"{k} : {'modifié' if now['informatif_non_strict']['documents'].get(k, {}).get('sha256') != v['sha256'] else 'identique'}" for k, v in frozen["informatif_non_strict"]["documents"].items()]
    if as_json:
        print(json.dumps({"ok": not diffs, "ecarts": diffs}, ensure_ascii=False, indent=1))
    else:
        print(f"PHASE_4_FROZEN — statut conservé : {frozen['statut_decision']} ({'; '.join(frozen['raisons_du_statut'])}) ; gel du {frozen['cree_le']}")
        counts = {g: len(frozen[g]) for g in ("code", "test_v1", "regles", "benchmark", "interfaces_et_fiches", "resultats_phase4", "modeles")}
        print("fichiers vérifiés :", counts, "| vecteurs :", len(frozen["index"]["vecteurs"]), "| corpus figé :", len(frozen["corpus"]["instantane_fichiers"]), "fichiers,",
              frozen["corpus"]["fichiers_sources_raw"]["n"], "sources raw")
        if diffs:
            for g, d in diffs.items():
                print(f"ÉCART [{g}] :", "; ".join(d[:6]), "…" if len(d) > 6 else "")
        else:
            print("RÉSULTAT : aucun écart — l'état gelé est exactement l'état actuel.")
        print("documents (informatifs, non stricts) :", "; ".join(info))
    return 1 if diffs else 0


def create() -> None:
    if MANIFEST.exists():
        sys.exit("REFUSÉ : le manifeste existe déjà ; un gel ne se réécrit pas.")
    man = collect()
    MANIFEST.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    MARKER.write_text("PHASE_4_FROZEN\n\nÉtat du système gelé pour la validation juridique (phase 5). Statut de décision : NO-GO PROVISOIRE (validation humaine absente, TEST v2 absent).\n"
                      f"Manifeste : agent_fr/eval/human/PHASE_4_FROZEN.manifest.json (SHA-256 {sha(MANIFEST)})\n"
                      "Vérifier : python -m agent_fr.eval.human.freeze_phase4 verify\nDocumentation : docs/PHASE_4_FROZEN.md\n"
                      "Ne plus modifier : embeddings, reranker, poids de fusion, chunking, règles de ranking, logique temporelle, seuils, notation, TEST v1.\n", encoding="utf-8")
    print("manifeste écrit :", MANIFEST, "|", sha(MANIFEST))
    print({g: len(man[g]) for g in ("code", "test_v1", "regles", "benchmark", "interfaces_et_fiches", "resultats_phase4", "modeles")}, "| durée", man["duree_collecte_s"], "s")


# ----------------------------------------------------------------------------------- reproductibilité
def repro(skip_llm=False) -> dict:
    import numpy as np
    out = {"date": time.strftime("%Y-%m-%dT%H:%M:%S"), "controles": {}}
    t = time.time()
    out["controles"]["1_empreintes"] = {"ok": verify(as_json=False) == 0, "duree_s": round(time.time() - t, 1)}
    # 2. ré-encodage COMPLET des vecteurs de l'instantané figé
    os.environ["AGENT_CORPUS_DIR"] = str(SNAP)
    from agent_fr.build_vectors import load_chunks, vectors_key
    from agent_fr.embed import Embedder, passage_text, vector_path
    t = time.time()
    ch = load_chunks(["fr", "ar"])
    V = np.load(vector_path(vectors_key(["fr", "ar"])))
    E = Embedder()
    Q = E.embed([passage_text(c) for c in ch], "passage: ")
    cos = np.sum(Q * V, axis=1) / (np.linalg.norm(Q, axis=1) * np.linalg.norm(V, axis=1))
    out["controles"]["2_vecteurs_reencodes"] = {"ok": bool(len(ch) == len(V) and cos.min() >= 0.9999), "chunks": len(ch), "cosinus_min": round(float(cos.min()), 8), "cosinus_moyen": round(float(cos.mean()), 8),
                                                "vecteurs_cos_inferieur_a_0_99999": int((cos < 0.99999).sum()), "duree_s": round(time.time() - t, 1)}
    # 3. reconstruction du corpus dans un dossier temporaire (raw par jonction, le corpus vivant n'est PAS touché)
    t = time.time()
    tmp = Path("D:/llm/tmp_repro_corpus")
    if tmp.exists():
        subprocess.run(["cmd", "/c", "rmdir", "/S", "/Q", str(tmp).replace("/", "\\")], capture_output=True)
    (tmp / "reports").mkdir(parents=True)
    for n in ("download_report.json", "crawl_report.json"):
        (tmp / "reports" / n).write_bytes((ROOT / "corpus" / "reports" / n).read_bytes())
    subprocess.run(["cmd", "/c", "mklink", "/J", str(tmp / "raw").replace("/", "\\"), str(ROOT / "corpus" / "raw").replace("/", "\\")], capture_output=True)
    code = ("import sys; sys.path.insert(0, r'" + str(ROOT) + "'); from pathlib import Path; import boa_pipeline.config as C; C.CORPUS = Path(r'" + str(tmp) + "'); "
            "from boa_pipeline.build import build; build()")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(ROOT))
    cmpf = {}
    for lg in ("fr", "ar", "und"):
        a, b = tmp / "chunks" / f"chunks_{lg}.jsonl", ROOT / "corpus" / "chunks" / f"chunks_{lg}.jsonl"
        cmpf[f"chunks_{lg}.jsonl"] = a.exists() and sha(a) == sha(b)
    docs_same = True
    for lg in ("fr", "ar", "und"):
        a, b = tmp / "metadata" / f"documents_{lg}.json", ROOT / "corpus" / "metadata" / f"documents_{lg}.json"
        if not (a.exists() and json.loads(a.read_text(encoding="utf-8")) == json.loads(b.read_text(encoding="utf-8"))):
            docs_same = False
    cmpf["documents_*.json (contenu JSON identique)"] = docs_same
    subprocess.run(["cmd", "/c", "rmdir", str(tmp / "raw").replace("/", "\\")], capture_output=True)     # retire la jonction SANS toucher à la cible
    subprocess.run(["cmd", "/c", "rmdir", "/S", "/Q", str(tmp).replace("/", "\\")], capture_output=True)
    out["controles"]["3_reconstruction_du_corpus"] = {"ok": all(cmpf.values()) and r.returncode == 0, "comparaisons": cmpf, "code_retour": r.returncode, "raw_intact": (ROOT / "corpus" / "raw").exists(),
                                                       "duree_s": round(time.time() - t, 1), "stderr": r.stderr[-300:] if r.returncode else ""}
    # 4. retrieval DEV rejoué = sorties enregistrées
    t = time.time()
    os.environ["AGENT_LLM"] = "local"
    from agent_fr.agent import get_index
    from agent_fr.pipelines import get_pipeline
    idx, search = get_index(), get_pipeline("hybrid_rerank")
    rec = {r["id"]: r for r in json.loads((RESULTS / "human_bench_dev_phase4.json").read_text(encoding="utf-8"))["records"]}
    bench = {}
    with open(HERE / "benchmark_dev_phase4.jsonl", encoding="utf-8") as f:
        for l in f:
            if l.strip():
                it = json.loads(l)
                bench[it["id"]] = it
    same = 0
    diff = []
    for iid, it in bench.items():
        res = search(idx, it["question"], 10)
        seen, ranked = set(), []
        for h in res.hits:
            key = (h.chunk["work_id"], h.chunk.get("article"))
            if key not in seen:
                seen.add(key)
                ranked.append(h.chunk["chunk_id"])
        old = [x["chunk_id"] for x in rec[iid]["retrieved"]]
        if ranked[:10] == old[:10] and res.found == rec[iid]["found"]:
            same += 1
        else:
            diff.append(iid)
    out["controles"]["4_retrieval_dev_rejoue"] = {"ok": not diff, "questions": len(bench), "identiques": same, "differentes": diff, "duree_s": round(time.time() - t, 1)}
    # 5. génération LLM rejouée SANS cache
    if not skip_llm:
        t = time.time()
        from agent_fr import answer
        ids = [i for i, r in rec.items() if r.get("mode") == "llm" and r.get("answer_found")][:6]
        same_ans, ans_diff, unavailable = 0, [], []
        for iid in ids:
            res = search(idx, bench[iid]["question"], 6)
            new = answer.llm(idx, res, 6)
            if new.get("mode") != "llm":                                          # serveur LLM éteint : repli extractif ; ce n'est PAS un résultat de reproductibilité
                unavailable.append(iid)
            elif (new.get("answer") or "") == (rec[iid]["answer"] or ""):
                same_ans += 1
            else:
                ans_diff.append(iid)
        out["controles"]["5_generation_llm_rejouee_sans_cache"] = {"ok": not ans_diff and not unavailable, "questions": ids, "identiques": same_ans, "differentes": ans_diff, "non_executees_llm_indisponible": unavailable,
                                                                   "duree_s": round(time.time() - t, 1),
                                                                   "note": "une différence signale que le décodage local n'est pas strictement déterministe (les sorties enregistrées restent la référence)"}
    os.environ.pop("AGENT_CORPUS_DIR", None)
    out["ok"] = all(c["ok"] for c in out["controles"].values())
    dst = RESULTS / "phase4_reproducibility.json"
    dst.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk in ("ok", "duree_s", "cosinus_min", "identiques", "questions", "differentes", "comparaisons")} for k, v in out["controles"].items()}, ensure_ascii=False, indent=1))
    print("écrit :", dst)
    return out


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("create")
    s = sp.add_parser("verify")
    s.add_argument("--json", action="store_true")
    s = sp.add_parser("repro")
    s.add_argument("--skip-llm", action="store_true")
    a = ap.parse_args()
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    if a.cmd == "create":
        create()
    elif a.cmd == "verify":
        sys.exit(verify(a.json))
    else:
        sys.exit(0 if repro(a.skip_llm)["ok"] else 1)


if __name__ == "__main__":
    main()
