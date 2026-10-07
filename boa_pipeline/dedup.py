"""Étape 9 : détection des doublons.

* même fichier (sha256) accessible depuis plusieurs URLs  -> un seul document canonique, URLs en `alias_urls`
* même texte normalisé dans des fichiers différents       -> signalé (pas fusionné : preuve de provenance différente)
* même work_id + langue, fichiers différents               -> versions/duplication éventuelle, signalé
"""
from collections import defaultdict

from .util import norm_for_hash, sha256_text


def dedup_files(docs: list[dict]):
    """Avant attribution des identifiants : fusionne les URLs pointant vers un fichier identique."""
    by_file = defaultdict(list)
    for d in docs:
        by_file[d["file_hash"]].append(d)
    canon, rep = [], {"identical_files": [], "identical_text_different_files": [], "same_work_same_language": []}
    for h, ds in by_file.items():
        ds.sort(key=lambda d: d["document_url"])
        main = ds[0]
        main["alias_urls"] = [{"document_url": x["document_url"], "source_url": x["source_url"], "title": x["title"]}
                              for x in ds[1:]]
        main["all_source_urls"] = sorted({x["source_url"] for x in ds} | {u for x in ds for u in x.get("all_source_urls", [])})
        if len(ds) > 1:
            rep["identical_files"].append({"file_hash": h, "kept": main["document_url"],
                                           "duplicates": [x["document_url"] for x in ds[1:]]})
        canon.append(main)
    return canon, rep


def dedup_text_and_versions(canon: list[dict], rep: dict):
    """Après attribution des identifiants : textes identiques / même texte juridique en plusieurs fichiers."""
    by_text = defaultdict(list)
    for d in canon:
        t = norm_for_hash(d.get("_full_text", ""))
        d["text_hash"] = sha256_text(t) if t else None
        if t and len(t) > 300:
            by_text[d["text_hash"]].append(d)
    for h, ds in by_text.items():
        if len(ds) > 1:
            rep["identical_text_different_files"].append({"text_hash": h, "documents": [x["document_id"] for x in ds],
                                                          "urls": [x["document_url"] for x in ds]})
            for d in ds:
                d.setdefault("quality_flags", []).append("texte_identique_a_un_autre_fichier")
    by_wl = defaultdict(list)
    for d in canon:
        by_wl[(d["work_id"], d["language"])].append(d)
    for k, ds in by_wl.items():
        if len(ds) > 1:
            rep["same_work_same_language"].append({"work_id": k[0], "language": k[1],
                                                   "documents": [x["document_id"] for x in ds],
                                                   "urls": [x["document_url"] for x in ds],
                                                   "action": "conservés tous (versions possibles) — vérification humaine"})
            for d in ds:
                d.setdefault("quality_flags", []).append("meme_texte_plusieurs_fichiers")
    rep["counts"] = {k: len(v) for k, v in rep.items() if isinstance(v, list)}
    return rep
