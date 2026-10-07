"""Relecture des résultats bout en bout : corrige les erreurs de la notation automatique (qui compare des chaînes littérales).

ATTENTION : relecture faite par un assistant IA (Claude), PAS par un juriste humain. Elle ne remplace pas une relecture humaine ; elle sert à borner l'erreur de la
notation automatique, qui a des faux négatifs (réponse juste mais formulée autrement que le fait clé : « 08% » / « 8 % », « six (06) mois » / « six (6) mois »,
« interdit de stipuler » / « interdit expressément de stipuler ») et des faux positifs (un seul des quatre textes modificateurs cités, réponse hésitante).

Règles (écrites avant d'appliquer le script, appliquées à TOUS les pipelines de la même façon) :
  1. Récupération (faux négatifs) : une question explicitement listée dans RECOVER est comptée juste si la réponse est juste ET si le critère de preuve est vérifié
     mécaniquement : regex trouvée dans le texte d'au moins un passage CITÉ (`support`) ou dans la réponse (`answer`).
  2. Rétrogradation (faux positifs), mécanique : (a) question « tous les textes attendus » (mode all) jugée juste alors qu'un texte attendu n'est pas cité ;
     (b) réponse jugée juste mais qui déclare elle-même que l'information « n'est pas directement/explicitement précisée ».
Usage : python -m agent_fr.eval.adjudicate   -> results/e2e_adjudication.json"""
import json
import os
import re
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
SNAP = Path(os.environ.get("AGENT_CORPUS_DIR", "D:/llm/snapshots/corpus_2026-10-06"))
PIPES = ("legacy", "hybrid", "hybrid_rerank")

# id -> (type de preuve, regex, justification courte). Choisis après lecture des réponses (voir docs/RETRIEVAL_PHASE2.md).
RECOVER = {
    "V006": ("support", r"inform\w+ le demandeur", "obligation d'informer le demandeur énoncée dans le passage cité"),
    "V007": ("support", r"clauses? p[ée]nales?", "interdiction des clauses pénales dans le passage cité ; l'adverbe « expressément » faisait échouer la comparaison littérale"),
    "V008": ("support", r"facturation .{0,40}interdite|interdite, sauf", "même règle dans un autre texte cité (REG-92-04 / REG-95-07), pas dans le texte attendu"),
    "V010": ("answer", r"600[ .\u00a0]?000", "liste bien les valeurs successives (600 000 puis 2 000 000) ; « deux millions » attendu en lettres"),
    "V012": ("support", r"7[ .\u00a0]?500|sept mille cinq cent", "identifie le règlement 16-02 et son modificateur 24-05, valeur dans le passage cité"),
    "V021": ("support", r"modifiant et compl[ée]tant le r[èe]glement n°\s?16", "texte modificateur correctement cité"),
    "V023": ("support", r"plafond", "nomme le bon règlement modificateur ; le fait clé « deux millions » n'était pas demandé par la question"),
    "V039": ("support", "\u0628\u0646\u0643 \u0627\u0644\u062c\u0632\u0627\u0626\u0631", "réponse arabe juste, texte cité différent du texte attendu mais pertinent"),
    "W005": ("support", r"six \(0?6\) mois", "six mois, dans un règlement qui complète le texte attendu ; « (06) » vs « (6) »"),
    "W013": ("answer", r"8\s?%.*6\s?%.*3\s?%", "les trois taux 8 %, 6 %, 3 % ; le fait clé était écrit « 08% »"),
    "X008": ("support", r"7[ .\u00a0]?500|sept mille cinq cent", "règle actuelle (REG-24-05) ; le gold visait le texte de 1995, daté"),
    "X009": ("support", r"soldes? d[ée]biteurs?", "même interdiction dans un autre texte cité (INS-06-21), pas le texte attendu"),
}
HEDGE = re.compile(r"n['’]est pas (?:directement|explicitement) (?:pr[ée]cis|mentionn|indiqu)", re.I)


def chunk_texts():
    out = {}
    for lg in ("fr", "ar"):
        for l in open(SNAP / f"chunks_{lg}.jsonl", encoding="utf-8"):
            c = json.loads(l)
            out[c["chunk_id"]] = c["text"]
    return out


def main():
    texts = chunk_texts()
    gold = {}
    for st in ("v3", "v4", "v5"):
        for l in open(HERE / f"gold_{st}.jsonl", encoding="utf-8"):
            r = json.loads(l)
            gold[r["id"]] = r
    out = {"avertissement": "Relecture par un assistant IA, pas par un juriste humain. Règles : voir agent_fr/eval/adjudicate.py.", "pipelines": {}}
    for p in PIPES:
        f = RES / f"e2e_{p}_v345.json"
        if not f.exists():
            continue
        det = json.loads(f.read_text(encoding="utf-8"))["details"]
        items, cat = {}, defaultdict(lambda: [0, 0, 0])
        for x in det:
            g = gold[x["id"]]
            auto = x["correct"]
            verdict, why = auto, ""
            if not auto and x["id"] in RECOVER and x["found"]:
                kind, rx, note = RECOVER[x["id"]]
                hay = x["reponse"] if kind == "answer" else " ".join(texts.get(c.replace(".fr~2", ".fr"), texts.get(c, "")) for c in x["citations"])
                if re.search(rx, hay, re.I | re.S):
                    verdict, why = True, "récupéré : " + note
            if auto and g.get("mode") == "all":
                cited_works = {c.split("::")[0].rsplit(".", 1)[0] for c in x["citations"]}
                missing = [e["work_id"] for e in g["expected"] if e["work_id"] not in cited_works]
                if missing:
                    verdict, why = False, "rétrogradé : textes attendus non cités " + ",".join(missing)
            if auto and verdict and HEDGE.search(x["reponse"]) and not g.get("expect_refuse"):
                verdict, why = False, "rétrogradé : la réponse dit elle-même que l'information n'est pas précisée"
            items[x["id"]] = {"auto": auto, "relu": verdict, "motif": why}
            cat[x["category"]][0] += int(verdict)
            cat[x["category"]][1] += 1
            cat[x["category"]][2] += int(auto)
        n = len(det)
        out["pipelines"][p] = {"n": n, "auto": sum(v["auto"] for v in items.values()), "relu": sum(v["relu"] for v in items.values()),
                               "recuperes": sorted(i for i, v in items.items() if v["relu"] and not v["auto"]),
                               "retrogrades": sorted(i for i, v in items.items() if v["auto"] and not v["relu"]),
                               "par_categorie": {c: {"relu": v[0], "auto": v[2], "n": v[1]} for c, v in sorted(cat.items())}, "items": items}
        print(f"{p:14} auto {out['pipelines'][p]['auto']}/{n}  relu {out['pipelines'][p]['relu']}/{n}  récupérés {out['pipelines'][p]['recuperes']}  rétrogradés {out['pipelines'][p]['retrogrades']}")
    (RES / "e2e_adjudication.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
