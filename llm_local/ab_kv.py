"""A/B de réglages du serveur sur un prompt réaliste d'agent (~1 400 tokens de sources) : vitesse (lecture du prompt, génération) et RAM.
Usage : python llm_local/ab_kv.py  (le serveur doit être arrêté ; le script lance lui-même chaque configuration)"""
import json
import subprocess
import sys
import time
from pathlib import Path

import psutil
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm_client import chat  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BIN = Path((Path("D:/llm/llama.cpp/CURRENT_TAG.txt")).read_text().strip())
EXE = Path("D:/llm/llama.cpp") / BIN / "llama-server.exe"
MODEL = "D:/llm/models/qwen3-4b-instruct-2507-q4_k_m.gguf"
PORT = 8187
chunks = [json.loads(l) for l in open(ROOT / "corpus/chunks/chunks_fr.jsonl", encoding="utf-8")][2000:2006]
ctx = "\n\n".join(f"<source id=\"S{i + 1}\">\n{c['text'][:1000]}\n</source>" for i, c in enumerate(chunks))
PROMPT = "Question : Quelles sont les obligations des banques d'après ces textes ?\n\n" + ctx
BASE = ["-m", MODEL, "-t", "8", "-tb", "8", "-c", "4096", "--host", "127.0.0.1", "--port", str(PORT), "-np", "1", "--no-webui", "-ngl", "0",
        "-b", "512", "-ub", "128", "-lm", "none", "-cram", "256", "-ctxcp", "2"]
CONFIGS = {
    "A_kv_q8_fa_on (actuel)": ["-ctk", "q8_0", "-ctv", "q8_0", "-fa", "on"],
    "B_kv_f16_fa_auto": [],
    "C_kv_f16_ub256": ["-ub", "256"],
}


def run(label, extra):
    p = subprocess.Popen([str(EXE)] + BASE + extra, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(60):
            time.sleep(1)
            try:
                if requests.get(f"http://127.0.0.1:{PORT}/health", timeout=2).json().get("status") == "ok":
                    break
            except Exception:
                pass
        rs = []
        for i in range(3):   # 3 passages : le 1er peut être froid ; on garde aussi les suivants
            r = chat([{"role": "user", "content": PROMPT + f"\n(passage {i})"}], url=f"http://127.0.0.1:{PORT}", max_tokens=100)
            rs.append(r)
        rss = max(psutil.Process(p.pid).memory_info().rss for _ in range(1)) / 1e6
        print(f"{label:28} prompt {rs[0]['prompt_n']} tok | PP tok/s {[x['prompt_tok_s'] for x in rs]} | TG tok/s {[x['gen_tok_s'] for x in rs]} | RAM serveur {rss:.0f} Mo")
    finally:
        p.terminate()
        p.wait(timeout=20)
        time.sleep(3)


for k, v in CONFIGS.items():
    run(k, v)
