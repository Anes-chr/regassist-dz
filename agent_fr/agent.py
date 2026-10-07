"""Point d'entrée de l'agent : ask(question) -> dict structuré.

Moteur de recherche : AGENT_RETRIEVER = auto (défaut) | hybrid_rerank | hybrid | hybrid_plain | vector | bm25 | legacy.
« auto » = hybride + reranker si les modèles et les vecteurs locaux sont présents ; sinon repli AUTOMATIQUE sur l'ancien moteur (legacy)
avec une note dans la réponse. L'ancien moteur n'est jamais supprimé : AGENT_RETRIEVER=legacy le force (rollback immédiat).
"""
import os

from . import answer
from .index import Index, _signature, load_index
from .pipelines import get_pipeline

_IDX: Index | None = None
_SIG: str | None = None
_FALLBACK_REASON: str | None = None      # mémorise une défaillance du moteur v2 pour ne pas la rejouer à chaque question


def get_index(force: bool = False) -> Index:
    """Recharge l'index automatiquement si le corpus a été reconstruit (le serveur n'a pas à être redémarré)."""
    global _IDX, _SIG
    sig = _signature()
    if _IDX is None or force or sig != _SIG:
        _IDX, _SIG = load_index(force), sig
    return _IDX


def retriever_name() -> str:
    return os.environ.get("AGENT_RETRIEVER", "auto").lower()


def search(idx: Index, question: str, k: int):
    """Recherche avec le moteur choisi ; en mode auto, repli sur legacy si le moteur v2 est indisponible."""
    global _FALLBACK_REASON
    name = retriever_name()
    if name in ("auto", "default"):
        name = "legacy" if _FALLBACK_REASON else "hybrid_rerank"
    if name == "legacy":
        res = get_pipeline("legacy")(idx, question, k)
        if _FALLBACK_REASON and retriever_name() in ("auto", "default"):
            res.notes = list(res.notes) + [f"Moteur de recherche de repli (lexical) utilisé : {_FALLBACK_REASON}"]
        return res
    try:
        return get_pipeline(name)(idx, question, k)
    except (FileNotFoundError, ImportError, OSError, RuntimeError, AssertionError) as e:
        if retriever_name() not in ("auto", "default"):
            raise
        _FALLBACK_REASON = f"{type(e).__name__}: {str(e)[:160]}"
        res = get_pipeline("legacy")(idx, question, k)
        res.notes = list(res.notes) + [f"Moteur de recherche de repli (lexical) utilisé : {_FALLBACK_REASON}"]
        return res


def ask(question: str, use_llm: bool = False, k: int = 6) -> dict:
    question = (question or "").strip()
    if len(question) < 3:
        return {"mode": "extractif", "found": False, "answer": "Posez une question sur un texte réglementaire.",
                "citations": [], "notes": [], "disclaimer": answer.DISCLAIMER, "reason": "question_vide"}
    idx = get_index()
    res = search(idx, question, k)
    out = answer.llm(idx, res, k) if use_llm else answer.extractive(idx, res, min(k, 5))
    out["retriever"] = "legacy" if (retriever_name() == "legacy" or _FALLBACK_REASON) else retriever_name().replace("auto", "hybrid_rerank")
    out["timings"] = getattr(res, "timings", {})
    return out
