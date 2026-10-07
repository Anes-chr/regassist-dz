"""Vérification d'intégrité du corpus FINAL (phase 3, étapes 1-10) : documents, échecs, doublons, OCR, langues, métadonnées, chunks, relations, vecteurs, cache vectoriel.
Rien n'est modifié : le script ne fait que LIRE et produit un rapport (results/corpus_check.json + .md). Les anomalies sont classées : BLOQUANT / A_CORRIGER / INFO.

Usage : python -m agent_fr.eval.human.corpus_check [--corpus DIR_PLAT_FIGÉ] [--live] [--out results/corpus_check]
  --corpus : instantané plat (chunks_*.jsonl, documents_*.json, legal_status.json) ; --live : corpus/ vivant (raw/, state/, reports/ inclus).
"""
import argparse
import hashlib
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
AR = re.compile(r"[؀-ۿݐ-ݿ]")
LAT = re.compile(r"[A-Za-zÀ-ÿ]")
CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f-�]")


def jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8")] if Path(p).exists() else []


def jdocs(p):
    if not Path(p).exists():
        return []
    d = json.loads(Path(p).read_text(encoding="utf-8"))
    return d if isinstance(d, list) else list(d.values())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=None)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "agent_fr" / "eval" / "results" / "corpus_check"))
    a = ap.parse_args()
    if a.corpus:
        base = Path(a.corpus)
        cdir = ddir = base
    else:
        cdir, ddir = ROOT / "corpus" / "chunks", ROOT / "corpus" / "metadata"
    chunks = {lg: jl(cdir / f"chunks_{lg}.jsonl") for lg in ("fr", "ar", "und")}
    docs = {lg: jdocs(ddir / f"documents_{lg}.json") for lg in ("fr", "ar", "und")}
    rep = {"corpus": a.corpus or "corpus vivant", "anomalies": []}

    def anomaly(level, kind, detail, n=None, examples=None):
        rep["anomalies"].append({"niveau": level, "type": kind, "detail": detail, "n": n, "exemples": (examples or [])[:6]})

    # --- 1. documents et tailles
    rep["documents"] = {lg: len(d) for lg, d in docs.items()}
    rep["chunks"] = {lg: len(c) for lg, c in chunks.items()}
    rep["textes_distincts"] = {lg: len({d["work_id"] for d in docs[lg]}) for lg in docs}
    allc = [c for lg in chunks for c in chunks[lg]]
    alld = [d for lg in docs for d in docs[lg]]
    rep["taille_chunks_car"] = {"mediane": int(np.median([c["char_count"] for c in allc])) if allc else 0, "max": max((c["char_count"] for c in allc), default=0)}
    # raw : fichiers présents et empreintes (corpus vivant)
    if a.live:
        missing, bad_hash = [], []
        for d in alld:
            rp = ROOT / "corpus" / d["raw_path"] if d.get("raw_path") else None
            if rp is None or not rp.exists():
                missing.append(d["document_id"])
            elif d.get("file_hash") and hashlib.sha256(rp.read_bytes()).hexdigest() != d["file_hash"]:
                bad_hash.append(d["document_id"])
        rep["raw"] = {"documents_sans_fichier": len(missing), "empreinte_differente": len(bad_hash)}
        if missing:
            anomaly("BLOQUANT", "fichier_source_absent", "document référencé sans fichier dans raw/", len(missing), missing)
        if bad_hash:
            anomaly("BLOQUANT", "empreinte_differente", "SHA-256 du fichier ≠ file_hash enregistré", len(bad_hash), bad_hash)
        # --- 2. échecs
        rpt = ROOT / "corpus" / "reports"
        fails = json.loads((rpt / "failed_documents.json").read_text(encoding="utf-8")) if (rpt / "failed_documents.json").exists() else []
        dl = json.loads((rpt / "download_report.json").read_text(encoding="utf-8")) if (rpt / "download_report.json").exists() else {}
        rep["echecs"] = {"documents_en_echec": len(fails), "telechargement": {k: (len(v) if isinstance(v, (list, dict)) else v) for k, v in dl.items()}}
        if fails:
            anomaly("A_CORRIGER", "documents_en_echec", "documents non extraits ou non téléchargés (voir failed_documents.json)", len(fails), [f.get("document_id") or f.get("url") for f in fails])
    # --- 3. doublons
    by_hash = defaultdict(list)
    for d in alld:
        if d.get("text_hash"):
            by_hash[d["text_hash"]].append(d["document_id"])
    dup_text = {h: v for h, v in by_hash.items() if len(v) > 1}
    copies = [d for d in alld if "~" in d["document_id"]]
    rep["doublons"] = {"textes_identiques_documents_differents": len(dup_text), "copies_~N": len(copies)}
    # copies d'un même texte avec des DATES différentes (anomalie de métadonnée)
    byw = defaultdict(list)
    for d in alld:
        byw[(d["work_id"], d.get("language"))].append(d)
    date_conflict = [w for (w, lg), v in byw.items() if len({x.get("date") for x in v if x.get("date")}) > 1]
    if date_conflict:
        anomaly("A_CORRIGER", "dates_differentes_pour_un_meme_texte", "même work_id, plusieurs dates (copies ou textes homonymes)", len(date_conflict), date_conflict)
    # --- 4. OCR
    ocr = Counter(d.get("extraction_method") for d in alld)
    rep["extraction"] = dict(ocr)
    garbled = [c["chunk_id"] for c in chunks["ar"] if len(c["text"]) > 150 and (len(AR.findall(re.sub(r"[\s\d]", "", c["text"]))) / max(1, len(re.sub(r"[\s\d]", "", c["text"]))) < 0.6)
               and len(LAT.findall(c["text"])) / max(1, len(c["text"])) < 0.15]
    ctrl = [c["chunk_id"] for c in allc if len(CTRL.findall(re.sub(r"\s", "", c["text"]))) / max(1, len(re.sub(r"\s", "", c["text"]))) > 0.03]
    rep["texte_illisible"] = {"chunks_arabes_peu_arabes": len(garbled), "chunks_caracteres_controle": len(ctrl)}
    if garbled or ctrl:
        anomaly("A_CORRIGER", "texte_illisible", "couche texte corrompue (lettres remplacées par des caractères de contrôle)", len(set(garbled) | set(ctrl)), sorted(set(garbled) | set(ctrl)))
    # --- 5. langues
    wrong = []
    for lg in ("fr", "ar"):
        for c in chunks[lg]:
            if len(c["text"]) < 120:
                continue
            ar_r = len(AR.findall(c["text"])) / len(c["text"])
            lat_r = len(LAT.findall(c["text"])) / len(c["text"])
            if lg == "fr" and ar_r > 0.3 or lg == "ar" and lat_r > 0.5 and ar_r < 0.15:
                wrong.append(c["chunk_id"])
    rep["langues"] = {"chunks_langue_incoherente": len(wrong)}
    if wrong:
        anomaly("INFO", "langue_incoherente", "chunk dont l'écriture dominante contredit la langue annotée (tableaux bilingues, annexes)", len(wrong), wrong)
    # --- 6. métadonnées
    miss = Counter()
    suspect_year = []
    for d in alld:
        for k in ("date", "number", "document_type", "title", "document_url", "source_url"):
            if not d.get(k):
                miss[k] += 1
        m4 = re.search(r"(?<!\d)(19[89]\d|20[0-3]\d)(?!\d)", str(d.get("number") or ""))      # année à 4 chiffres dans le numéro (« 09-2016 », « 2017-01 »)
        if d.get("date") and m4 and abs(int(d["date"][:4]) - int(m4.group(1))) > 1:
            suspect_year.append(d["document_id"])
    rep["metadonnees"] = {"champs_manquants": dict(miss), "date_incoherente_avec_le_numero": len(suspect_year)}
    if suspect_year:
        anomaly("A_CORRIGER", "date_suspecte", "l'année du numéro (ex. 01-2023) diffère de plus d'un an de la date enregistrée (ex. 2016-09-01 par défaut)", len(suspect_year), suspect_year)
    if miss.get("date"):
        anomaly("INFO", "date_manquante", "documents sans date", miss["date"])
    # --- 7. chunks
    ids = Counter(c["chunk_id"] for c in allc)
    dupids = [k for k, v in ids.items() if v > 1]
    rep["chunks_controle"] = {"identifiants_en_double": len(dupids), "chunks_vides": sum(1 for c in allc if not c["text"].strip()), "sans_texte_avec_contexte": sum(1 for c in allc if not c.get("text_with_context"))}
    if dupids:
        anomaly("BLOQUANT", "chunk_id_non_unique", "identifiants de chunks dupliqués : un identifiant doit être stable, déterministe et UNIQUE (phase 4)", len(dupids), dupids)
    # --- 8. relations
    wk = {d["work_id"] for d in alld}
    recip_missing, unresolved, future = 0, 0, []
    inv = {"abroge": "abroge_par", "modifie": "modifie_par", "complete": "complete_par", "remplace": "remplace_par"}
    dmap = {d["work_id"]: d for d in alld}
    for d in alld:
        for k, k2 in inv.items():
            for e in d.get(k, []):
                w = e.get("work_id")
                if not w:
                    unresolved += 1
                    continue
                tgt = dmap.get(w)
                if tgt is None:
                    unresolved += 1
                elif not any(x.get("work_id") == d["work_id"] for x in tgt.get(k2, [])):
                    recip_missing += 1
                elif tgt.get("date") and d.get("date") and d["date"] < tgt["date"]:
                    future.append(f"{d['work_id']}->{w}")
    rep["relations"] = {"cibles_non_resolues": unresolved, "reciproques_manquantes": recip_missing, "texte_modificateur_anterieur_a_sa_cible": len(future)}
    if future:
        anomaly("A_CORRIGER", "relation_date_incoherente", "un texte « modifie/abroge » un texte plus récent que lui", len(future), future)
    # --- 8 bis. jumeaux FR/AR : un texte arabe de même type + même numéro qu'un texte français UNIQUE doit lui être rattaché (même work_id) ; les conflits de dates documentés restent des exceptions
    from boa_pipeline.relations import num_key
    fr_by = {}
    for d in docs["fr"]:
        if d.get("number"):
            fr_by.setdefault((d["type_code"], num_key(d["number"])), set()).add(d["work_id"])
    fr_works = {d["work_id"] for d in docs["fr"]}
    unpaired, exceptions = [], []
    for d in docs["ar"] + docs["und"]:
        if d["work_id"] in fr_works or not d.get("number"):
            continue
        cand = fr_by.get((d["type_code"], num_key(d["number"])), set())
        if cand:
            (exceptions if str(d.get("twin_status", "")).startswith("CONFLIT_DE_DATE") else unpaired).append(d["document_id"])
    rep["jumeaux_ar"] = {"ar_sans_jumeau_de_meme_work_id": sum(1 for d in docs["ar"] + docs["und"] if d["work_id"] not in fr_works),
                         "non_rattaches_avec_candidat_fr": len(unpaired), "exceptions_documentees_conflit_de_date": len(exceptions), "exceptions": exceptions}
    if unpaired:
        anomaly("A_CORRIGER", "jumeau_ar_non_rattache", "document arabe de même type + même numéro qu'un texte français, sans conflit de date documenté", len(unpaired), unpaired)
    if exceptions:
        anomaly("INFO", "jumeau_ar_conflit_de_date", "même type + même numéro qu'un texte français mais dates complètes différentes : NON tranché automatiquement (proposition dans boa_pipeline/twin_overrides.json, arbitrage humain)", len(exceptions), exceptions)
    # --- 8 ter. relations FR / AR d'un même texte : mêmes cibles
    by_w = {}
    for d in alld:
        by_w.setdefault(d["work_id"], []).append(d)
    incoh = []
    for w, ds in by_w.items():
        langs = {d["language"] for d in ds}
        if {"fr", "ar"} <= langs:
            sig = {lg: {(k, e.get("work_id")) for d in ds if d["language"] == lg for k in inv for e in d.get(k, [])} for lg in ("fr", "ar")}
            if sig["fr"] != sig["ar"]:
                incoh.append(w)
    rep["relations_fr_ar"] = {"textes_bilingues": sum(1 for ds in by_w.values() if {"fr", "ar"} <= {d["language"] for d in ds}), "relations_differentes_entre_langues": len(incoh)}
    if incoh:
        anomaly("A_CORRIGER", "relations_fr_ar_incoherentes", "les versions FR et AR d'un même texte portent des relations différentes", len(incoh), incoh)
    # --- 8 quater. liens morts (rapport du build) et OCR_UNCERTAIN
    dl = (Path(a.corpus) / "dead_links.json") if a.corpus else ROOT / "corpus" / "reports" / "dead_links.json"
    if dl.exists():
        dead = json.loads(dl.read_text(encoding="utf-8"))
        rep["liens_morts"] = {"uniques": len(dead), **dict(Counter(x["resolution"] for x in dead))}
        broken = [x["url"] for x in dead if x["resolution"] == "BROKEN_SOURCE"]
        if broken:
            anomaly("A_CORRIGER", "source_cassee", "lien mort sans source officielle retrouvée (BROKEN_SOURCE) : document absent du corpus", len(broken), broken)
        moved = [x["url"] for x in dead if x["resolution"] == "MOVED_OFFICIAL"]
        if moved:
            anomaly("INFO", "lien_deplace", "ancien chemin du site /pdf/… ; le même fichier est dans le corpus sous son URL officielle actuelle (pas un document manquant)", len(moved), moved)
    unc = [c for c in allc if c.get("ocr_uncertain")]
    rep["ocr_uncertain"] = {"chunks": len(unc), "documents": len({c["document_id"] for c in unc}), "jetons": sum(len(c["ocr_uncertain_tokens"]) for c in unc)}
    if unc:
        anomaly("INFO", "ocr_uncertain", "chunks arabes (OCR) dont une valeur numérique n'est pas corroborée par le texte français : signalés, jamais corrigés", len(unc), sorted({c["document_id"] for c in unc}))
    # --- statut juridique
    lf = (Path(a.corpus) / "legal_status.json") if a.corpus else ROOT / "corpus" / "metadata" / "legal_status.json"
    if lf.exists():
        L = json.loads(lf.read_text(encoding="utf-8"))
        rep["statut_juridique"] = L["stats"]
    else:
        anomaly("BLOQUANT", "statut_absent", "legal_status.json absent : python -m agent_fr.legal_status")
    # --- 9/10. vecteurs
    try:
        from agent_fr.embed import INDEX_DIR, corpus_key
        from agent_fr.build_vectors import vectors_key
        import os
        if a.corpus:
            os.environ["AGENT_CORPUS_DIR"] = a.corpus
        key = vectors_key(["fr", "ar"])
        vp = INDEX_DIR / f"vec_{key}.npy"
        if vp.exists():
            V = np.load(vp)
            n_expected = len(chunks["fr"]) + len(chunks["ar"])
            norms = np.linalg.norm(V, axis=1)
            rep["vecteurs"] = {"fichier": str(vp), "n": int(V.shape[0]), "attendus": n_expected, "dim": int(V.shape[1]), "nan": int(np.isnan(V).sum()), "norme_min": float(norms.min()), "norme_max": float(norms.max())}
            if V.shape[0] != n_expected or np.isnan(V).any() or abs(norms.min() - 1) > 1e-3 or abs(norms.max() - 1) > 1e-3:
                anomaly("BLOQUANT", "vecteurs_incoherents", "nombre, NaN ou normes anormales")
            # cache : mêmes empreintes que les textes ; recalcul de 20 vecteurs au hasard
            cache = INDEX_DIR / "vec_cache_e5small.npz"
            if cache.exists():
                z = np.load(cache, allow_pickle=False)
                hs = z["hashes"].tolist()
                rep["cache_vecteurs"] = {"entrees": len(hs), "doublons_empreinte": len(hs) - len(set(hs))}
                from agent_fr.embed import Embedder, passage_text
                texts = [passage_text(c) for c in chunks["fr"] + chunks["ar"]]
                rnd = random.Random(3)
                sample = rnd.sample(range(len(texts)), min(20, len(texts)))
                emb = Embedder(4).embed([texts[i] for i in sample], prefix="passage: ")
                cosv = [float(emb[j] @ V[i]) for j, i in enumerate(sample)]
                rep["cache_vecteurs"]["recalcul_20_vecteurs_cos_min"] = round(min(cosv), 6)
                if min(cosv) < 0.9999:
                    anomaly("BLOQUANT", "vecteurs_obsoletes", "un vecteur stocké diffère du recalcul (texte modifié sans ré-encodage ?)", n=sum(1 for c in cosv if c < 0.9999))
        else:
            anomaly("BLOQUANT", "vecteurs_absents", f"{vp} absent : python -m agent_fr.build_vectors")
    except Exception as e:                                                  # modèle ou onnxruntime absent
        anomaly("A_CORRIGER", "controle_vecteurs_impossible", f"{type(e).__name__}: {str(e)[:120]}")
    rep["synthese"] = dict(Counter(x["niveau"] for x in rep["anomalies"]))
    Path(a.out + ".json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    md = ["# Contrôle d'intégrité du corpus", "", f"Corpus : {rep['corpus']}", "", f"Synthèse : {rep['synthese']}", "", "| Niveau | Type | n | Détail |", "|---|---|---:|---|"]
    for x in rep["anomalies"]:
        md.append(f"| {x['niveau']} | {x['type']} | {x['n'] if x['n'] is not None else ''} | {x['detail']} ; ex. {', '.join(map(str, x['exemples'][:3]))} |")
    Path(a.out + ".md").write_text("\n".join(md), encoding="utf-8")
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps({k: v for k, v in rep.items() if k not in ("anomalies",)}, ensure_ascii=False, indent=1)[:3000])
    for x in rep["anomalies"]:
        print(f"[{x['niveau']}] {x['type']} n={x['n']} : {x['detail']} ; {x['exemples'][:3]}")


if __name__ == "__main__":
    main()
