"""Fournisseurs de LLM interchangeables pour l'agent.

  AGENT_LLM=anthropic (défaut)  API distante Anthropic ; clé dans ANTHROPIC_API_KEY ; modèle AGENT_MODEL (défaut claude-sonnet-5-5)
  AGENT_LLM=local               llama-server local (Qwen3-4B-Instruct-2507 Q4_K_M sur CPU) ; URL dans AGENT_LOCAL_URL
                                (défaut http://127.0.0.1:8187) ; démarrage : llm_local\\start_server.ps1

Le profil « local » envoie moins de passages et des extraits plus courts : sur CPU, chaque token d'entrée coûte du temps.
"""
import os
import time

import requests

PROFILE = {
    "anthropic": {"k": 6, "excerpt": 1800, "max_tokens": 1200},
    "local": {"k": 4, "excerpt": 1000, "max_tokens": 600, "max_chars": 6400},   # 6400 car ≈ 2,25 car./jeton : 4096 - 600 (réponse) - 484 (consigne) ≈ 2 980 jetons
}


SCHEMA = {"type": "object", "additionalProperties": False, "required": ["found", "answer", "citations"],
          "properties": {"found": {"type": "boolean"}, "answer": {"type": "string"},
                         "citations": {"type": "array", "items": {"type": "string", "pattern": "^S[0-9]+$"}}}}


class BackendUnavailable(Exception):
    """Le fournisseur demandé n'est pas utilisable (clé absente, serveur éteint…) : l'agent retombe sur la réponse extractive."""


def provider() -> str:
    """LLM LOCAL par défaut. L'API distante (anthropic) n'est utilisable qu'avec AGENT_LLM=anthropic ET AGENT_ALLOW_REMOTE_LLM=1 : le corpus ne doit pas
    quitter la machine sans autorisation explicite (règle du projet, phase 2/3)."""
    p = os.environ.get("AGENT_LLM", "local").lower()
    return p if p in PROFILE else "local"


def remote_allowed() -> bool:
    return os.environ.get("AGENT_ALLOW_REMOTE_LLM", "") == "1"


def local_url() -> str:
    return os.environ.get("AGENT_LOCAL_URL", "http://127.0.0.1:8187").rstrip("/")


def complete(system: str, user: str, prov: str | None = None) -> dict:
    """Retourne {text, model, latency_s, provider}. Lève BackendUnavailable si le fournisseur n'est pas prêt."""
    prov = prov or provider()
    prof = PROFILE[prov]
    t0 = time.time()
    if prov == "local":
        url = local_url()
        try:
            ok = requests.get(url + "/health", timeout=3).json().get("status") == "ok"
        except Exception:
            ok = False
        if not ok:
            raise BackendUnavailable(f"LLM local demandé mais llama-server ne répond pas sur {url} : lancez llm_local\\start_server.ps1 "
                                     "(réponse extractive affichée).")
        rf = ({"type": "json_object"} if os.environ.get("AGENT_JSON_SCHEMA", "1") == "0" else
              {"type": "json_schema", "json_schema": {"name": "reponse", "strict": True, "schema": SCHEMA}})   # décodage contraint par grammaire
        body = {"model": "local", "temperature": 0, "max_tokens": prof["max_tokens"], "cache_prompt": True, "response_format": rf,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        r = requests.post(url + "/v1/chat/completions", json=body, timeout=900)
        if getattr(r, "status_code", 200) == 400 and rf["type"] == "json_schema":          # serveur sans json_schema : repli json_object
            body["response_format"] = {"type": "json_object"}
            r = requests.post(url + "/v1/chat/completions", json=body, timeout=900)
        r.raise_for_status()
        j = r.json()
        return {"text": j["choices"][0]["message"]["content"].strip(),
                "model": os.environ.get("AGENT_LOCAL_MODEL_NAME", "qwen3-4b-instruct-2507-q4_k_m (local, CPU)"),
                "latency_s": round(time.time() - t0, 1), "provider": "local", "timings": j.get("timings", {})}
    if not remote_allowed():
        raise BackendUnavailable("API distante refusée : les passages du corpus ne sont envoyés à aucun service externe sans autorisation explicite "
                                 "(définir AGENT_ALLOW_REMOTE_LLM=1 pour l'autoriser). Réponse extractive affichée.")
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise BackendUnavailable("Mode LLM demandé mais ANTHROPIC_API_KEY est absente : réponse extractive. "
                                 "(Pour un LLM local : définir AGENT_LLM=local ou utiliser --local-llm.)")
    import anthropic
    model = os.environ.get("AGENT_MODEL", "claude-sonnet-5-5")
    client = anthropic.Anthropic(api_key=key)
    msg = client.messages.create(model=model, max_tokens=prof["max_tokens"], temperature=0, system=system,
                                 messages=[{"role": "user", "content": user}])
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text").strip()
    return {"text": text, "model": model, "latency_s": round(time.time() - t0, 1), "provider": "anthropic"}
