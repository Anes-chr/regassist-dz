"""Registre des pipelines de recherche. Chaque pipeline : f(idx, question, k) -> retrieve.Result.

  legacy   : recherche d'origine (BM25 + références + relations + refus lexical) — CONSERVÉE comme référence et repli
Les autres pipelines (BM25 pur, vectoriel, hybride, hybride + reranker) sont enregistrés par agent_fr.retrieve2 lorsqu'il est importable.
La variable d'environnement AGENT_RETRIEVER choisit le pipeline utilisé par l'agent (défaut : legacy tant qu'un autre n'est pas validé).
"""
import os

from . import retrieve as _legacy


def _legacy_search(idx, question, k=6):
    return _legacy.search(idx, question, k)


PIPELINES = {"legacy": _legacy_search}


def get_pipeline(name: str | None = None):
    name = name or os.environ.get("AGENT_RETRIEVER", "legacy")
    if name not in PIPELINES:
        try:
            from . import retrieve2  # noqa: F401  (enregistre bm25 / vector / hybrid / rerank)
        except ImportError:
            pass
    if name not in PIPELINES:
        raise KeyError(f"pipeline inconnu : {name} (disponibles : {sorted(PIPELINES)})")
    return PIPELINES[name]
