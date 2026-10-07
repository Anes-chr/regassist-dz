"""Client minimal pour llama-server (API compatible OpenAI) : streaming, temps jusqu'au 1er token, timings serveur, RAM du processus."""
import json
import time

import requests

try:
    import psutil
except ImportError:  # facultatif
    psutil = None

DEFAULT_URL = "http://127.0.0.1:8187"


def server_pid_rss(url_port: int = 8080):
    """RAM (Mo) du processus llama-server, si psutil est installé."""
    if not psutil:
        return None
    for p in psutil.process_iter(["name", "memory_info"]):
        if (p.info["name"] or "").lower().startswith("llama-server"):
            return round(p.info["memory_info"].rss / 1e6)
    return None


def chat(messages, url: str = DEFAULT_URL, max_tokens: int = 400, temperature: float = 0.0, json_mode: bool = False,
         timeout: int = 600, schema: dict | None = None) -> dict:
    """Retourne {text, ttft_s, total_s, prompt_tok_s, gen_tok_s, prompt_n, gen_n, rss_mb}."""
    body = {"model": "local", "messages": messages, "max_tokens": max_tokens, "temperature": temperature,
            "stream": True, "stream_options": {"include_usage": True}, "cache_prompt": True}
    if schema:
        body["response_format"] = {"type": "json_schema", "json_schema": {"name": "reponse", "strict": True, "schema": schema}}
    elif json_mode:
        body["response_format"] = {"type": "json_object"}
    t0 = time.time()
    ttft = None
    text, timings, usage = [], {}, {}
    with requests.post(url + "/v1/chat/completions", json=body, stream=True, timeout=timeout) as r:
        r.raise_for_status()
        for raw in r.iter_lines():
            if not raw or not raw.startswith(b"data:"):
                continue
            payload = raw[5:].strip()
            if payload == b"[DONE]":
                break
            ev = json.loads(payload)
            if ev.get("timings"):
                timings = ev["timings"]
            if ev.get("usage"):
                usage = ev["usage"]
            for ch in ev.get("choices", []):
                piece = (ch.get("delta") or {}).get("content")
                if piece:
                    if ttft is None:
                        ttft = time.time() - t0
                    text.append(piece)
    total = time.time() - t0
    return {"text": "".join(text), "ttft_s": round(ttft, 2) if ttft else None, "total_s": round(total, 2),
            "prompt_tok_s": round(timings.get("prompt_per_second", 0), 1), "gen_tok_s": round(timings.get("predicted_per_second", 0), 1),
            "prompt_n": timings.get("prompt_n", usage.get("prompt_tokens")), "gen_n": timings.get("predicted_n", usage.get("completion_tokens")),
            "rss_mb": server_pid_rss()}


def health(url: str = DEFAULT_URL) -> bool:
    try:
        return requests.get(url + "/health", timeout=3).json().get("status") == "ok"
    except Exception:
        return False
