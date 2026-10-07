"""Benchmark juridique indépendant (phase 3) : schéma, chargement, vérification mécanique contre le corpus, règles de notation.

RÈGLES DE NOTATION — fixées AVANT la première exécution sur le benchmark et NON modifiées ensuite pour améliorer un score (voir docs/RETRIEVAL_PHASE3.md) :

  Retrieval (questions à réponse attendue) : rang du premier passage attendu (texte, article) dans le classement dédoublonné ; « tous » pour les questions multi-textes.
    Recall@1/3/5/10, MRR ;  exactitude documentaire (texte attendu dans le top-k) ;  exactitude article (texte+article dans le top-k) ;
    exactitude temporelle (le passage n°1 est une version acceptable, et aucune version interdite n'est classée avant la 1re version acceptable) ;
    exactitude juridique (le passage n°1 n'est pas une version interdite ET son statut calculé n'est pas ABROGATED/REPLACED/HISTORICAL, sauf si ce statut est attendu).
  Réponse finale correcte  =  C1 ∧ C2 ∧ C3 ∧ C4 ∧ C5 :
    C1 répond : tous les faits clés sont dans la réponse (comparaison normalisée : minuscules, espaces/ponctuation/parenthèses supprimés, zéros de tête ignorés ; une entrée
       de faits_cles peut être une liste d'alternatives) ;
    C2 supportée : chaque fait clé figure aussi dans au moins une source CITÉE ; une « source » = le bloc complet donné au modèle (passage + référence, titre, statut juridique et
       relations : un numéro de texte modificateur n'est que dans les métadonnées) [précision ajoutée après la 1re exécution DEV, avant TEST ; non rétroactive sur le fond de la règle] ;
    C3 bonne version : aucune source citée n'est une version interdite, et au moins une source citée est une version acceptable ;
    C4 citation correcte : au moins un passage attendu (ou version acceptable) est cité ; pour les questions multi-textes, tous les textes attendus sont cités ;
    C5 rien hors contexte : tout nombre (≥ 2 chiffres, chiffres arabes-indiens convertis) et tout numéro d'article cité dans la réponse figure dans les sources données au modèle (même bloc complet) ou dans la question.
  Refus / clarification : comportement attendu = « refuser » (found=false), « clarifier » (clarify=true) ; sinon « répondre ».
  Statut correct : le statut calculé de la source principale citée est égal au statut attendu (jugé par un humain), ET la réponse ou ses notes signalent tout statut ≠ ACTIVE/MODIFIED.
Les relectures humaines peuvent diverger de ces règles ; les divergences sont documentées, les règles ne sont pas retouchées.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

TYPES = ["A_direct", "B_multi_textes", "C_temporelle", "D_modification", "E_abrogation", "F_comparaison", "G_ambigue", "H_hors_corpus", "I_hors_sujet", "J_fr_ar"]
STATUTS = ["ACTIVE", "MODIFIED", "REPLACED", "ABROGATED", "HISTORICAL", "UNKNOWN"]
COMPORTEMENTS = ["repondre", "refuser", "clarifier"]
DIFFICULTES = ["facile", "moyen", "difficile"]
LANGUES = ["fr", "ar"]
REQUIRED = ["id", "split", "type_de_question", "question", "langue", "domaine", "document_attendu", "article_attendu", "passage_attendu", "reponse_attendue",
            "date_de_reference", "statut_juridique", "niveau_de_difficulte", "attendu_comportement", "validation_humaine", "redaction"]


def norm_text(s: str) -> str:
    s = str(s).replace("’", "'").replace("‘", "'").replace(" ", " ").replace(" ", " ").lower()
    return re.sub(r"\s+", " ", s).strip()


def norm_fact(s: str) -> str:
    """Normalisation des faits clés (voir l'en-tête) : insensible à la casse, aux espaces, à la ponctuation, aux parenthèses et aux zéros de tête."""
    s = norm_text(s)
    s = re.sub(r"[\s().,;:«»\"'\-–—/]", "", s)
    return re.sub(r"(?<!\d)0+(?=\d)", "", s)


def fact_ok(answer: str, fact) -> bool:
    alts = fact if isinstance(fact, list) else [fact]
    a = norm_fact(answer)
    return any(norm_fact(f) in a for f in alts)


def load(path) -> list[dict]:
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def sha256(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Corpus:
    """Chunks FR+AR, documents, statut juridique calculé du corpus évalué."""

    def __init__(self, directory=None):
        if directory:
            d = Path(directory)
            cf, ca, df, lf = d / "chunks_fr.jsonl", d / "chunks_ar.jsonl", d / "documents_fr.json", d / "legal_status.json"
            da = d / "documents_ar.json"
        else:
            cf, ca = ROOT / "corpus/chunks/chunks_fr.jsonl", ROOT / "corpus/chunks/chunks_ar.jsonl"
            df, da, lf = ROOT / "corpus/metadata/documents_fr.json", ROOT / "corpus/metadata/documents_ar.json", ROOT / "corpus/metadata/legal_status.json"
        self.dir = directory
        self.chunks = [json.loads(l) for p in (cf, ca) if p.exists() for l in open(p, encoding="utf-8")]
        docs = []
        for p in (df, da):
            if p.exists():
                x = json.loads(p.read_text(encoding="utf-8"))
                docs += x if isinstance(x, list) else list(x.values())
        self.docs = {}
        for d in docs:
            self.docs.setdefault(d["work_id"], d)
        self.by_key = {}
        for c in self.chunks:
            if "~" in c["document_id"]:
                continue
            self.by_key.setdefault((c["work_id"], c.get("article")), []).append(c)
            self.by_key.setdefault((c["work_id"], None), []).append(c)
        from agent_fr.legal_status import Legal
        self.legal = Legal(json.loads(lf.read_text(encoding="utf-8")) if lf.exists() else None)

    def find_passage(self, work_id, article, quote):
        q = norm_text(quote)
        for c in self.by_key.get((work_id, article), []):
            if q in norm_text(c["text"]):
                return c
        return None


def verify_item(it: dict, corpus: Corpus) -> list[str]:
    """Problèmes bloquants (liste vide = item cohérent avec le corpus). La validité JURIDIQUE reste à valider par un humain."""
    p = []
    for k in REQUIRED:
        if k not in it:
            p.append(f"champ manquant : {k}")
    if p:
        return p
    if it["type_de_question"] not in TYPES:
        p.append("type_de_question inconnu")
    if it["split"] not in ("DEV", "TEST"):
        p.append("split invalide")
    if it["langue"] not in LANGUES:
        p.append("langue invalide")
    if it["attendu_comportement"] not in COMPORTEMENTS:
        p.append("attendu_comportement invalide")
    if it["niveau_de_difficulte"] not in DIFFICULTES:
        p.append("niveau_de_difficulte invalide")
    if it["statut_juridique"] is not None and it["statut_juridique"] not in STATUTS:
        p.append("statut_juridique invalide")
    if it["attendu_comportement"] == "repondre":
        if not it["passage_attendu"] or not it["reponse_attendue"]:
            p.append("question à réponse attendue sans passage_attendu / reponse_attendue")
        for ps in it["passage_attendu"]:
            c = corpus.find_passage(ps["work_id"], ps.get("article"), ps["citation"])
            if c is None:
                p.append(f"passage introuvable : {ps['work_id']} art. {ps.get('article')} « {ps['citation'][:50]}… »")
        for fk in it.get("faits_cles", []):
            alts = fk if isinstance(fk, list) else [fk]
            texts = " ".join(c["text"] for ps in it["passage_attendu"] for c in corpus.by_key.get((ps["work_id"], ps.get("article")), []))
            ans = it["reponse_attendue"]
            if not any(norm_fact(a) in norm_fact(texts) or norm_fact(a) in norm_fact(ans) for a in alts):
                p.append(f"fait clé absent du passage et de la réponse attendue : {fk}")
        for dk in it.get("document_attendu", []):
            if dk["work_id"] not in corpus.docs:
                p.append(f"document inconnu : {dk['work_id']}")
    else:
        if it["passage_attendu"]:
            p.append("question à refuser/clarifier avec passage_attendu")
    vh = it["validation_humaine"]
    if vh.get("statut") not in ("en_attente", "valide", "corrige", "rejete"):
        p.append("validation_humaine.statut invalide")
    return p


def computed_status(corpus: Corpus, work_id, article):
    chunks = corpus.by_key.get((work_id, article)) or corpus.by_key.get((work_id, None)) or []
    if not chunks:
        return None
    return corpus.legal.status_for_chunk(chunks[0])["statut"]


def main():
    """Vérification mécanique d'un fichier benchmark contre un corpus + manifeste (empreinte, répartition). Usage : python -m agent_fr.eval.human.bench B.jsonl [--corpus DIR]"""
    import argparse
    from collections import Counter
    ap = argparse.ArgumentParser()
    ap.add_argument("bench")
    ap.add_argument("--corpus", default=None)
    ap.add_argument("--manifest", action="store_true", help="écrit <bench>.manifest.json")
    a = ap.parse_args()
    corpus = Corpus(a.corpus)
    items = load(a.bench)
    bad = 0
    for it in items:
        pb = verify_item(it, corpus)
        if pb:
            bad += 1
            print(it.get("id"), "|", "; ".join(pb))
    ids = [i["id"] for i in items]
    if len(ids) != len(set(ids)):
        print("identifiants en double")
        bad += 1
    man = {"fichier": str(a.bench), "sha256": sha256(a.bench), "n": len(items), "par_split": dict(Counter(i["split"] for i in items)),
           "par_type": dict(Counter(i["type_de_question"] for i in items)), "par_langue": dict(Counter(i["langue"] for i in items)),
           "validation_humaine": dict(Counter(i["validation_humaine"]["statut"] for i in items)), "problemes": bad,
           "corpus": a.corpus or "corpus vivant"}
    print(json.dumps(man, ensure_ascii=False))
    if a.manifest:
        Path(str(a.bench) + ".manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
