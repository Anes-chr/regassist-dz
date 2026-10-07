"""Fiches pour le juriste, générées DEPUIS les données figées (aucune valeur recopiée à la main) — phase 5, gel de validation :
  docs/CAS_CRITIQUES_A_EXAMINER.md + review/cas_critiques_a_examiner.csv  (H120, H129 ; H130 et les « métadonnées internes » en rappel)
  docs/ARBITRAGE_JUMEAUX_FR_AR.md  + review/arbitrage_jumeaux_fr_ar.csv    (REG-90-01, REG-02-01, REG-06-01 : aucune date n'est choisie)
  review/corpus_index_for_jurist.csv                                         (annuaire des 1 085 documents avec URL officielle)
Rien n'est corrigé, rien n'est rejoué : les sorties lues sont celles de human_bench_dev_final2.json (phase 3) et human_bench_dev_phase4.json (phase 4).
Usage : python -m agent_fr.eval.human.build_case_sheets"""
import csv
import json
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RES = ROOT / "agent_fr" / "eval" / "results"
REVIEW = HERE / "review"
DOCS = ROOT / "docs"
SNAP = Path("D:/llm/snapshots/corpus_phase4")
BENCH = HERE / "benchmark_v1_draft.jsonl"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def jl(p):
    with open(p, encoding="utf-8") as f:                       # PAS splitlines() : il coupe aussi sur des séparateurs Unicode présents dans le texte des chunks
        return [json.loads(l) for l in f if l.strip()]


def h2g(y, m, d):
    """Calendrier hégirien tabulaire (± 1-2 jours) -> date grégorienne ISO. Vérification de cohérence, pas une preuve."""
    import datetime
    jd = d + math.ceil(29.5 * (m - 1)) + (y - 1) * 354 + (3 + 11 * y) // 30 + 1948439.5 - 1
    return datetime.date.fromordinal(int(round(jd - 1721424.5))).isoformat()


def clip(t, n=420):
    t = re.sub(r"\s+", " ", t or "").strip()
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + " […]"


def src_block(sources, cited):
    out = []
    for s in sources:
        mark = " **(citée)**" if s["chunk_id"] in cited else ""
        out.append(f"* **[{s['id']}]**{mark} {s['work_id']}, article {s['article']} — statut calculé par le système : {s.get('statut_juridique')}\n  > {clip(s['texte'], 380)}")
    return "\n".join(out)


def cases():
    bench = {i["id"]: i for i in jl(BENCH)}
    r3 = {x["id"]: x for x in load(RES / "human_bench_dev_final2.json")["records"]}
    r4 = {x["id"]: x for x in load(RES / "human_bench_dev_phase4.json")["records"]}
    s3 = {x["id"]: x for x in load(RES / "human_score_dev_final2.json")["items"]}
    s4 = {x["id"]: x for x in load(RES / "human_score_dev_phase4.json")["items"]}
    sample = set(json.loads((REVIEW / "human_eval_sample.json").read_text(encoding="utf-8")))
    fr = {}
    for c in jl(SNAP / "chunks_fr.jsonl"):
        if "~" not in c["document_id"] and c.get("article"):
            fr.setdefault((c["work_id"], c["article"]), c["text"])
    L = []
    P = L.append
    P("# Cas critiques à examiner attentivement")
    P("")
    P("**Statut du système : NO-GO PROVISOIRE** (validation humaine absente, TEST v2 absent). Ces cas **ne sont corrigés ni automatiquement ni à la main** : ils sont soumis au juriste et au benchmark indépendant. "
      "Les observations « techniques » ci-dessous sont celles d'une IA (non humaine) et ne préjugent d'aucune qualification juridique.")
    P("")
    P("Les deux cas ne figurent **pas** dans l'échantillon des 60 réponses de `human_eval_p4.html` (la phase 3 refusait de répondre à H120 et H129 n'a pas été tiré) : c'est pourquoi leurs sorties complètes sont reproduites ici. "
      "Fiche de réponse : `agent_fr/eval/human/review/cas_critiques_a_examiner.csv` (à renvoyer remplie ; enregistrement : `python -m agent_fr.eval.human.annotations ingest-sheet --file <fiche.csv>`).")
    P("")
    for cid, titre in (("H120", "H120 — compte en devises « débiteur » (question en arabe)"), ("H129", "H129 — taux « actuel » des réserves obligatoires (question en arabe)")):
        b = bench[cid]
        P(f"## {titre}")
        P("")
        P(f"**Question** ({b['type_de_question']}, difficulté {b['niveau_de_difficulte']}, langue {b['langue']}) : {b['question']}")
        P("")
        P("**Attendu (rédigé par une IA, non validé)** : " + "; ".join(f"{d['work_id']} article {a['article']}" for d, a in zip(b["document_attendu"], b["article_attendu"])) +
          f" ; date de référence : {b['date_de_reference'] or 'aucune'} ; statut attendu : {b['statut_juridique'] or 'non précisé'}")
        P(f"* Réponse attendue : {b['reponse_attendue']}")
        for ps in b["passage_attendu"]:
            P(f"* Passage attendu (texte français officiel) : « {ps['citation']} » — {fr.get((ps['work_id'], ps.get('article')), '')[:250]}")
        if b.get("versions_interdites"):
            P("* Versions à ne PAS présenter comme actuelles (liste du benchmark, par article) : " + ", ".join(f"{v['work_id']} art. {v['article']}" for v in b["versions_interdites"]))
        P("")
        if cid == "H120":
            P("**Évolution** : *avant la correction du parsing* (phase 3) → **refus à tort** ; *après la correction* (phase 4) → **réponse hors sujet** (voir ci-dessous).")
        else:
            P("**Problème actuel** : *valeur périmée* → *présentée comme actuelle* → *la notation automatique ne la considère pas comme erreur critique*.")
        P("")
        for tag, R, S, lab in (("P3", r3, s3, "Phase 3 (sortie gelée `human_bench_dev_final2.json`)"), ("P4", r4, s4, "Phase 4 (sortie `human_bench_dev_phase4.json`)")):
            r, s = R[cid], S[cid]
            P(f"### {lab}")
            P("")
            P(f"* Réponse : « {clip(r['answer'], 700)} »")
            P(f"* Passages cités : {', '.join(r['citations']) or 'aucun'} ; rang du passage attendu dans la recherche : {s['rank']}")
            P(f"* Notes du système : {' | '.join(n[:200] for n in r['notes']) or 'aucune'}")
            P(f"* Notation automatique : réponse correcte = {s.get('reponse_correcte')} ; refus à tort = {s.get('refus_a_tort')} ; hallucination = {s.get('hallucination')} ; erreur temporelle critique = {s.get('erreur_temporelle_critique')} ; statut correct = {s.get('statut_correct')}")
            P("* Passages donnés au modèle :")
            P(src_block(r["sources"], set(r["citations"])))
            P("")
        P("### Observations techniques (IA, non humaines ; aucune correction appliquée)")
        P("")
        if cid == "H120":
            P("* Le passage attendu (REG-09-01, article 4) est classé **premier** dans les deux phases et fait partie du contexte. Son texte arabe est abîmé par l'OCR (« رصيد عدين » pour « رصيد مدين », mots parasites) ; le texte français officiel dit que ces comptes « ne peuvent en aucun cas présenter un solde débiteur ».")
            P("* En phase 3 le modèle a refusé. En phase 4, les articles arabes de l'instruction INS-06-21 sont détectés (1 → 15 articles) : son article 3 (« compte devise commerçant / professionnel non commerçant : pas de soldes débiteurs ») entre dans le contexte (S4) et c'est lui que le modèle cite. "
              "Cette instruction vise une **autre catégorie de comptes** que REG-09-01 ; la réponse écrit « solde en crédit » alors que le passage parle de « soldes débiteurs » (أرصدة مدينة).")
            P("* La question emploie « الأشخاص المذكورين » (« les personnes mentionnées ») sans antécédent : c'est peut-être une question ambiguë (à apprécier par le juriste).")
            P("")
            P("### Questions au juriste (H120)")
            P("")
            P("1. La question est-elle juridiquement valide (et bien posée) ? ")
            P("2. La source retrouvée par le système (INS-06-21 art. 3) est-elle pertinente pour cette question ? La source attendue (REG-09-01 art. 4) l'est-elle ?")
            P("3. La réponse produite est-elle juridiquement correcte ? Contient-elle une hallucination ?")
            P("4. Le système aurait-il dû refuser ?")
        else:
            P("* Phase 3 : le modèle cite INS-02-21 art. 2 (valeur arabe abîmée « 2.90 ») ; la règle automatique signale une erreur temporelle critique (le texte cité est dans la liste des versions interdites).")
            P("* Phase 4 : le modèle cite **INS-02-23, « article 3 »**. Ce chunk arabe est le texte **cité** par l'instruction (« L'article 3 … est modifié et rédigé comme suit : « Article 3 : … 3 % … » ») : la détection d'en-têtes d'articles arabes, corrigée en phase 4, a "
              "découpé l'article 2 d'INS-02-23 au niveau de l'article cité et l'a étiqueté « article 3 ». Le statut juridique calculé pour « INS-02-23 art. 3 » est **ACTIVE**, car aucun texte ne modifie l'article 3 *de INS-02-23* ; le texte "
              "visé (article 3 d'INS-02-04) a pourtant été remplacé depuis (INS-09-25 : 2 %, puis INS-01-26 : 1 %). Le modèle recopie « ACTIVE ». L'instruction actuelle INS-01-26 n'est pas retrouvée en arabe (sa valeur est abîmée par l'OCR : « د 1 % »).")
            P("* La notation automatique ne signale pas d'erreur temporelle critique en phase 4 (le texte cité est l'article 3 alors que la liste des versions interdites désigne l'article 2) et juge même le **statut correct** (ACTIVE calculé = ACTIVE attendu) : "
              "**divergence entre la notation automatique et l'analyse qualitative**. La règle de notation n'est pas modifiée.")
            P("* Indicateur approximatif de l'ampleur (analyse, non corrigé) : environ 20 chunks arabes (15 documents) suivent immédiatement un chunk qui se termine par une ouverture de citation « ; 14 existaient déjà en phase 3.")
            P("")
            P("### Questions au juriste (H129)")
            P("")
            P("1. La question est-elle juridiquement valide ? La valeur attendue (1 %, INS-01-26) est-elle la bonne valeur « actuelle » ?")
            P("2. La réponse (3 %, présentée comme valeur actuelle et « ACTIVE ») est-elle une **erreur juridique critique**, ou une autre catégorie (précisez) ?")
            P("3. La version temporelle est-elle correcte ? La citation est-elle correcte (article cité) ?")
            P("4. Le juriste confirme-t-il l'écart entre la notation automatique (pas d'erreur critique, statut correct) et son analyse ?")
        P("")
    P("## Rappel : autres cas déjà signalés (à qualifier aussi)")
    P("")
    P("| Cas | Pourquoi | Dans l'échantillon de 60 ? |\n|---|---|---|")
    P(f"| H130 | taux directeur en arabe : « 902.75 % » au lieu de 2,75 % (OCR : « % » lu « 90 ») ; la réponse porte maintenant l'alerte `OCR_UNCERTAIN` | {'oui' if 'H130' in sample else 'non'} |")
    for cid in ("H041", "H055", "H039", "H053"):
        P(f"| {cid} | la réponse recopie une date de référence de la consigne interne (« métadonnée interne » ?) : à qualifier par le juriste, non tranché | {'oui' if cid in sample else 'non'} |")
    P("")
    return "\n".join(L) + "\n", cases_csv_rows()


def cases_csv_rows():
    return [["cas", "juriste", "question_juridiquement_valide", "source_retrouvee_pertinente", "reponse_juridiquement_correcte", "version_temporelle_correcte", "citation_correcte",
             "hallucination", "le_systeme_aurait_du_refuser", "qualification", "commentaire"],
            ["H120", "", "", "", "", "", "", "", "", "", ""], ["H129", "", "", "", "", "", "", "", "", "", ""], ["H130", "", "", "", "", "", "", "", "", "", ""]]


def conflicts():
    docs = {}
    for lg in ("fr", "ar"):
        raw = load(SNAP / f"documents_{lg}.json")
        for d in raw if isinstance(raw, list) else raw.values():
            docs[d["document_id"]] = d
    prop = load(ROOT / "boa_pipeline" / "twin_overrides.json")["proposals"]
    pairs = [("REG-90-01", "REG-90-01-19900704.fr", "REG-90-01-19900604.ar", (1410, 12, 12), "4 juin 1990 (4 يونيو)"),
             ("REG-02-01", "REG-02-01-20020217.fr", "REG-02-01-20020220.ar", None, "20 février 2002"),
             ("REG-06-01", "REG-06-01-20060907.fr", "REG-06-01-20060514.ar", (1427, 4, 16), "14 mai 2006")]
    L, P, rows = [], None, []
    P = L.append
    P("# Arbitrage humain : trois textes arabes / français en conflit de dates")
    P("")
    P("**Statut du système : NO-GO PROVISOIRE.** Pour ces trois textes, le français et l'arabe portent des **dates complètes différentes**. L'IA **ne choisit ni la date française ni la date arabe** : les deux documents restent des textes distincts dans le corpus "
      "tant que vous n'avez pas arbitré. Rien dans le pipeline n'applique votre décision automatiquement : elle se matérialise par une saisie explicite dans `boa_pipeline/twin_overrides.json` (champ `confirmed`, `confirmed_by` renseigné) puis une reconstruction.")
    P("")
    P("Fiche de réponse : `agent_fr/eval/human/review/arbitrage_jumeaux_fr_ar.csv` (enregistrement : `python -m agent_fr.eval.human.annotations ingest-sheet --file <fiche.csv>`).")
    P("")
    for tid, fid, aid, hij, ar_greg in pairs:
        f, a = docs[fid], docs[aid]
        pr = next(p for p in prop if p["fr_url"] == f["document_url"] and p["ar_url"] == a["document_url"])
        fr_txt = (ROOT / "corpus" / f["extracted_text_path"]).read_text(encoding="utf-8")
        ar_txt = (ROOT / "corpus" / a["extracted_text_path"]).read_text(encoding="utf-8")
        P(f"## {tid}")
        P("")
        P("| | Français | Arabe |\n|---|---|---|")
        P(f"| Document | {f['document_id']} | {a['document_id']} |")
        P(f"| Intitulé du site | {clip(f['title'], 150)} | {clip(a['title'], 110)} |")
        P(f"| **Date** | **{f['date']}** (source : {f.get('date_source')}) | **{a['date']}** (source : {a.get('date_source')}) |")
        P(f"| Source (PDF officiel) | {f['document_url']} | {a['document_url']} |")
        P(f"| Page du site qui le liste | {f['source_url']} | {a['source_url']} |")
        P(f"| Fichier local / pages / extraction | `corpus/{f['raw_path']}` / {f.get('page_count')} / {f['extraction_method']} | `corpus/{a['raw_path']}` / {a.get('page_count')} / {a['extraction_method']} |")
        P("")
        P(f"**Raison du conflit** : {pr['conflit']}.")
        P("")
        P("Éléments factuels (relevés par l'IA, non conclusifs) :")
        P("* " + pr["elements_factuels"][0].upper() + pr["elements_factuels"][1:].rstrip(".") + ".")
        P(f"* Éléments qui s'y opposent : {pr['elements_contraires'].rstrip('.')}.")
        P(f"* En-tête du PDF français (début du texte extrait) : « {clip(fr_txt.replace('[[PAGE 1]]', ''), 260)} »")
        P(f"* En-tête du PDF arabe (début du texte extrait par OCR) : « {clip(ar_txt.replace('[[PAGE 1]]', ''), 260)} »")
        if hij:
            P(f"* Date hégirienne imprimée dans le PDF arabe : {hij[2]}/{hij[1]}/{hij[0]} H ; au calendrier tabulaire (± 2 jours) : {h2g(*hij)}. À vérifier avec un convertisseur de référence.")
        P("")
        P("**Votre arbitrage** : la date de référence est-elle celle du français, celle de l'arabe, s'agit-il de **deux textes distincts**, ou est-ce **indéterminé** ? (colonnes `reference_correcte` : FR / AR / DEUX_TEXTES_DISTINCTS / INDETERMINE ; commentaire obligatoire pour les deux dernières.)")
        P("")
        rows.append([tid, "", "", "", f["date"], a["date"], f["document_url"], a["document_url"], pr["conflit"]])
    return "\n".join(L) + "\n", [["texte", "juriste", "reference_correcte", "date_de_reference_retenue", "date_FR_du_corpus", "date_AR_du_corpus", "source_FR", "source_AR", "raison_du_conflit", "commentaire"]] + [r + [""] for r in rows]


def corpus_index():
    L = load(SNAP / "legal_status.json")
    out = [["document_id", "work_id", "type", "numero", "date", "origine_de_la_date", "langue", "intitule", "pdf_officiel", "page_du_site", "extraction", "statut_juridique_calcule", "chunks_OCR_UNCERTAIN"]]
    unc = {}
    for lg in ("fr", "ar", "und"):
        for c in jl(SNAP / f"chunks_{lg}.jsonl"):
            if c.get("ocr_uncertain"):
                unc[c["document_id"]] = unc.get(c["document_id"], 0) + 1
    for lg in ("fr", "ar", "und"):
        d = load(SNAP / f"documents_{lg}.json")
        for x in d if isinstance(d, list) else d.values():
            st = (L["documents"].get(x["work_id"]) or {}).get("statut", "")
            out.append([x["document_id"], x["work_id"], x["document_type"], x.get("number") or "", x.get("date") or "", x.get("date_source") or "", x["language"], clip(x["title"], 160),
                        x["document_url"], x["source_url"], x["extraction_method"], st, unc.get(x["document_id"], "")])
    return out


def write_csv(p, rows):
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f, delimiter=";").writerows(rows)


def main():
    REVIEW.mkdir(exist_ok=True)
    md, rows = cases()
    (DOCS / "CAS_CRITIQUES_A_EXAMINER.md").write_text(md, encoding="utf-8")
    write_csv(REVIEW / "cas_critiques_a_examiner.csv", rows)
    md, rows = conflicts()
    (DOCS / "ARBITRAGE_JUMEAUX_FR_AR.md").write_text(md, encoding="utf-8")
    write_csv(REVIEW / "arbitrage_jumeaux_fr_ar.csv", rows)
    idx = corpus_index()
    write_csv(REVIEW / "corpus_index_for_jurist.csv", idx)
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    print("écrit : docs/CAS_CRITIQUES_A_EXAMINER.md, docs/ARBITRAGE_JUMEAUX_FR_AR.md, review/cas_critiques_a_examiner.csv, review/arbitrage_jumeaux_fr_ar.csv, review/corpus_index_for_jurist.csv (", len(idx) - 1, "documents )")


if __name__ == "__main__":
    main()
