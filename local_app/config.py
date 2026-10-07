"""Configuration de la couche applicative locale (phase 6).

Cette couche ENVELOPPE le système gelé (PHASE_4_FROZEN) : elle appelle `agent_fr.agent.ask` telle quelle, ne change aucun paramètre du moteur
et n'écrit rien dans le corpus, l'index, les modèles ni les jeux de test. Rien ici n'est lu par le moteur.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:                      # `python -m local_app` lancé depuis un autre dossier
    sys.path.insert(0, str(ROOT))

HOST = "127.0.0.1"                                  # constante, jamais configurable : l'application n'écoute que sur la boucle locale
DEFAULT_PORT = 8790                                 # 3000 (Grafana) et 8000 (IncrediBuild) sont occupés sur cette machine ; 8765 = ancienne interface Flask

MIN_QUESTION_CHARS = 3                              # = seuil de l'agent (`ask` : question vide sous 3 caractères)
MAX_QUESTION_CHARS = 500                            # = limite déjà appliquée par l'interface existante (agent_fr/app.py : question[:500])
MAX_BODY_BYTES = 8 * 1024

STATIC_DIR = Path(__file__).resolve().parent / "static"
RUNTIME_DIR = Path(os.environ.get("LOCAL_APP_RUNTIME", str(Path(__file__).resolve().parent / "runtime")))
LOG_FILE = RUNTIME_DIR / "api.log"

FREEZE_MARKER = ROOT / "PHASE_4_FROZEN"
FREEZE_MANIFEST = ROOT / "agent_fr" / "eval" / "human" / "PHASE_4_FROZEN.manifest.json"

LLM_UNAVAILABLE_MESSAGE = "Le modèle local n'est pas disponible. Veuillez démarrer llama-server."       # message d'ADMINISTRATION (route /api/status, scripts) : jamais affiché à l'utilisateur
LLM_UNAVAILABLE_PUBLIC = "Le service de rédaction des réponses est momentanément indisponible."         # message destiné à l'utilisateur (réponses de /api/chat, interface)
# Phrase affichée quand le système n'a pas de réponse directe mais a retrouvé des textes (génération impossible ou refus du modèle) : elle introduit la liste des textes décrits.
NO_DIRECT_ANSWER_MESSAGE = "Je ne peux pas répondre directement, mais voici quelques textes qui pourraient vous aider à trouver la réponse :"

# Question de contrôle jouée une fois au démarrage pour vérifier RÉELLEMENT que la recherche hybride et le reranker répondent (pas d'appel au LLM).
WARMUP_QUESTION = "Quel est le plafond d'indemnisation par déposant ?"


def port() -> int:
    raw = os.environ.get("LOCAL_APP_PORT", str(DEFAULT_PORT))
    try:
        p = int(raw)
    except ValueError:
        raise SystemExit(f"LOCAL_APP_PORT invalide : {raw!r}")
    if not 1024 <= p <= 65535:
        raise SystemExit(f"LOCAL_APP_PORT hors de la plage 1024-65535 : {p}")
    return p


def debug() -> bool:
    """Mode développement : ajoute aux réponses les champs internes (scores, empreinte du contexte) et journalise les piles d'erreur. Désactivé par défaut."""
    return os.environ.get("LOCAL_APP_DEBUG", "") == "1"


def log_questions() -> bool:
    """Par défaut le texte des questions n'est PAS écrit dans le journal (seulement sa longueur). LOCAL_APP_LOG_QUESTIONS=1 l'y écrit en clair."""
    return os.environ.get("LOCAL_APP_LOG_QUESTIONS", "") == "1"


# Variables qui modifient le comportement du moteur gelé (seuils, poids, modèles, jeux de données, moteur, mode de décodage).
# Si l'une d'elles est définie dans l'environnement, l'application refuse de démarrer : elle servirait un système qui n'est plus PHASE_4_FROZEN.
ENGINE_ENV = ("AGENT_RETRIEVER", "AGENT_RERANK_N", "AGENT_W_RERANK", "AGENT_RR_MIN", "AGENT_LANGS", "AGENT_RERANK_DIR", "AGENT_RERANK_MODEL",
              "AGENT_EMBED_DIR", "AGENT_VECTOR_DIR", "AGENT_JSON_SCHEMA")
# Variables neutralisées PAR L'APPLICATION dans son propre processus (le LLM est local, jamais distant).
REMOTE_ENV = ("AGENT_ALLOW_REMOTE_LLM", "ANTHROPIC_API_KEY", "AGENT_MODEL")
