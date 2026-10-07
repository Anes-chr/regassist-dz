"""Tests d'INTÉGRATION RÉELS : aucun faux. Navigateur -> API -> agent -> recherche hybride -> reranker -> llama-server -> réponse -> navigateur.
Exige llama-server en ligne (127.0.0.1:8187). Deux modes :
  * LOCAL_APP_URL=http://127.0.0.1:8790 : teste le déploiement déjà démarré par .\\start_local.ps1 ;
  * sans variable : démarre sa propre instance (port libre, journaux dans un dossier temporaire) puis l'arrête.
Lancer : python local_app/tests/test_integration.py   (affiche « Tests intégration : X/Y »)."""
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
from pathlib import Path

import psutil
import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

Q_REAL = "Quel est le plafond d'indemnisation par déposant ?"
Q_REFUS = "Quelle est la capitale de la France ?"
Q_VAGUE = "Que dit le règlement ?"
LOOPBACK = {"127.0.0.1", "::1", "::ffff:127.0.0.1"}
WIN_PATH = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Target:
    """L'application testée : déploiement existant (LOCAL_APP_URL) ou instance démarrée par ce test."""

    def __init__(self, env_extra=None):
        self.proc = None
        url = os.environ.get("LOCAL_APP_URL")
        if url and not env_extra:
            self.url, self.runtime = url.rstrip("/"), ROOT / "local_app" / "runtime"
            self.port = int(url.rsplit(":", 1)[1])
        else:
            self.port = free_port()
            self.url = f"http://127.0.0.1:{self.port}"
            self.runtime = Path(tempfile.mkdtemp(prefix="local_app_it_"))
            env = dict(os.environ, LOCAL_APP_PORT=str(self.port), LOCAL_APP_RUNTIME=str(self.runtime), PYTHONIOENCODING="utf-8", **(env_extra or {}))
            self.out, self.err = open(self.runtime / "out.txt", "w", encoding="utf-8"), open(self.runtime / "err.txt", "w", encoding="utf-8")
            self.proc = subprocess.Popen([sys.executable, "-m", "local_app"], cwd=ROOT, env=env, stdout=self.out, stderr=self.err)

    def wait_ready(self, timeout=300):
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.proc is not None and self.proc.poll() is not None:
                raise RuntimeError("l'application s'est arrêtée : " + (self.runtime / "err.txt").read_text(encoding="utf-8", errors="replace")[-400:])
            try:
                st = requests.get(self.url + "/api/status", timeout=3).json()
                if st["app"]["state"] != "starting":
                    return st
            except Exception:
                pass
            time.sleep(1)
        raise RuntimeError("l'application n'est pas prête")

    @property
    def pid(self) -> int:
        if self.proc is not None:
            return self.proc.pid
        for c in psutil.net_connections(kind="inet"):
            if c.status == "LISTEN" and c.laddr.port == self.port and c.pid:
                return c.pid
        raise RuntimeError("PID du serveur introuvable")

    def stop(self):
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        for f in ("out", "err"):
            if hasattr(self, f):
                getattr(self, f).close()


T: Target = None            # type: ignore
RESULTS = {}


def chat(question, timeout=400):
    return requests.post(T.url + "/api/chat", json={"question": question}, timeout=timeout)


def sample_remote_peers(pid, stop, seen):
    p = psutil.Process(pid)
    while not stop.is_set():
        try:
            for c in p.net_connections(kind="inet"):
                if c.raddr:
                    seen.add((c.raddr.ip, c.raddr.port))
        except psutil.Error:
            pass
        time.sleep(0.2)


def test_stack_is_ready_with_a_real_llm_and_no_remote_llm():
    st = T.wait_ready()
    assert st["app"]["state"] == "ready", st["app"]
    assert st["agent"]["ready"] and st["retrieval"]["ready"] and st["retrieval"]["engine"] == "hybrid_rerank" and st["reranker"]["ready"]
    assert st["llm"]["online"] is True, "llama-server doit être en ligne (lancer llm_local\\start_server.ps1) : " + json.dumps(st["llm"])
    assert st["llm"]["model_matches_expected"] is True and st["llm"]["provider"] == "local" and st["remote_llm"] is False
    assert st["phase"] == "PHASE_4_FROZEN" and st["status"] == "NO-GO PROVISOIRE"
    RESULTS["status"] = st


def test_real_question_end_to_end_through_the_api():
    seen, stop = set(), threading.Event()
    th = threading.Thread(target=sample_remote_peers, args=(T.pid, stop, seen), daemon=True)
    th.start()
    t0 = time.time()
    r = chat(Q_REAL)
    wall = time.time() - t0
    stop.set()
    th.join(2)
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    RESULTS["real"], RESULTS["real_wall_s"], RESULTS["peers"] = d, wall, seen
    assert d["status"] == "answered" and d["found"] is True and d["mode"] == "llm" and d["provider"] == "local" and "qwen" in d["model"].lower()
    assert d["retriever"] == "hybrid_rerank" and "rerank_ms" in d["timings"], d["timings"]              # le reranker a réellement tourné
    assert re.search(r"2[.\s ]?000[.\s ]?000|deux millions", d["answer"]), d["answer"]
    ids = {s["id"] for s in d["sources"]}
    assert d["citations"] and {c["id"] for c in d["citations"]} <= ids
    assert set(re.findall(r"\[(S\d+)\]", d["answer"])) <= ids and re.findall(r"\[S\d+\]", d["answer"]), "la réponse doit citer ses sources"
    assert all(s["document_url"].startswith("https://www.bank-of-algeria.dz/") and s["extrait"] and s["texte"] for s in d["sources"])
    du = d["durations_ms"]
    assert du["generation"] > 1000 and du["reranking"] > 0 and du["retrieval"] is not None and du["pipeline"] >= du["generation"] and du["api"] >= du["pipeline"]
    assert not WIN_PATH.search(json.dumps(d)) and "Traceback" not in json.dumps(d)
    assert d["llm"] == {"requested": True, "available": True, "message": None}


def test_no_connection_leaves_this_computer_during_a_real_question():
    seen = RESULTS["peers"]
    assert seen, "aucune connexion observée : l'échantillonnage ne fonctionne pas"
    assert {ip for ip, _ in seen} <= LOOPBACK, f"connexion(s) hors boucle locale : {sorted(seen)}"
    assert ("127.0.0.1", 8187) in seen or ("::ffff:127.0.0.1", 8187) in seen, f"le LLM local (127.0.0.1:8187) n'a pas été contacté : {sorted(seen)}"


def test_server_and_llama_server_listen_on_loopback_only():
    pid = T.pid
    listening = [c for c in psutil.Process(pid).net_connections(kind="inet") if c.status == "LISTEN"]
    assert listening and all(c.laddr.ip in ("127.0.0.1",) for c in listening), [(c.laddr.ip, c.laddr.port) for c in listening]
    assert {c.laddr.port for c in listening} == {T.port}
    ll = [c for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower().startswith("llama-server") for c in p.net_connections(kind="inet") if c.status == "LISTEN"]
    assert ll and all(c.laddr.ip == "127.0.0.1" for c in ll), [(c.laddr.ip, c.laddr.port) for c in ll]
    all_listen = [(c.laddr.ip, c.laddr.port) for c in psutil.net_connections(kind="inet") if c.status == "LISTEN" and c.pid in {pid} | {p.pid for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower().startswith("llama-server")}]
    assert all(ip == "127.0.0.1" for ip, _ in all_listen), all_listen


def test_api_is_a_transparent_wrapper_of_the_frozen_pipeline():
    from agent_fr import agent                                               # le moteur gelé, appelé directement, sans la couche applicative
    from local_app import service as S
    direct = agent.ask(Q_REAL, use_llm=True)
    api = RESULTS["real"]
    assert direct["found"] == api["found"] and direct["mode"] == api["mode"] and direct["retriever"] == api["retriever"]
    assert direct["answer"] == api["answer"], (direct["answer"], api["answer"])
    assert [c["chunk_id"] for c in direct["sources"]] == [s["chunk_id"] for s in api["sources"]]
    assert [c["id"] for c in direct["citations"]] == [c["id"] for c in api["citations"]]
    assert S.clean_notes(direct["notes"]) == api["notes"]
    for d_s, a_s in zip(direct["sources"], api["sources"]):                   # les champs transmis sont identiques à ceux du moteur (rien n'est réécrit)
        for k in ("texte", "titre", "article", "date", "page", "extrait", "statut", "statut_juridique", "statut_detail", "document_url", "source_url", "relations", "alerte"):
            assert d_s[k] == a_s[k], k


def test_real_refusal_and_ambiguous_question():
    r = chat(Q_REFUS)
    d = r.json()
    assert r.status_code == 200 and d["status"] == "refused" and d["found"] is False and d["sources"] == [] and d["citations"] == []
    assert d["answer"].startswith("Je ne trouve pas de disposition correspondante") and d["durations_ms"]["generation"] is None      # refus décidé par la recherche : le LLM n'est pas sollicité
    r = chat(Q_VAGUE)
    d = r.json()
    assert r.status_code == 200 and d["status"] == "clarification" and d["clarify"] is True and "trop générale" in d["answer"]


def test_real_broad_question_gives_either_an_answer_or_described_texts_never_a_bare_failure():
    """Question large réelle (celle qui fait dépasser au LLM local le plafond de 600 jetons). Le résultat dépend du modèle ; l'invariant testé est celui de l'application :
    pas de réponse directe  =>  la phrase « Je ne peux pas répondre directement… » + les textes retrouvés, décrits à partir de leurs métadonnées."""
    r = chat("donne moi les evolutions des valeurs de droit de change")
    d = r.json()
    RESULTS["broad"] = d
    assert r.status_code == 200 and d["status"] in ("answered", "llm_unavailable", "refused"), d["status"]
    if d["status"] == "answered":
        assert d["texts"] == [] and d["texts_intro"] is None
        return
    assert d["sources"], "pas de réponse directe : des textes doivent avoir été retrouvés pour être proposés"
    assert d["texts_intro"] == "Je ne peux pas répondre directement, mais voici quelques textes qui pourraient vous aider à trouver la réponse :"
    assert d["texts"] and sum(len(t["passages"]) for t in d["texts"]) == len(d["sources"])          # tous les passages sont rattachés à un texte
    for t in d["texts"]:
        assert t["reference"] and t["titre"] and t["type"] and t["date"] and t["passages"] and t["document_url"].startswith("https://www.bank-of-algeria.dz/")
        assert t["statut_juridique"] in ("ACTIVE", "MODIFIED", "REPLACED", "ABROGATED", "HISTORICAL", "UNKNOWN")
    raw = json.dumps(d["texts"], ensure_ascii=False)
    assert "chunk_id" not in raw and "score" not in raw and not WIN_PATH.search(raw)
    msgs = [n for n in d["notes"] if "rédigée" in n or "rédaction" in n]
    assert len(msgs) <= 1, d["notes"]                                                                 # une seule cause affichée, jamais deux messages redondants
    assert not re.search(r"llama|LLM|rerank|hybride|modèle local|OCR_UNCERTAIN|\[règle|qwen", json.dumps({"n": d["notes"], "m": d["llm"]["message"], "i": d["texts_intro"]}, ensure_ascii=False), re.I)


def test_status_and_health_stay_responsive_and_a_second_question_is_refused_while_generating():
    box = {}
    th = threading.Thread(target=lambda: box.update(r=chat(Q_REAL)))
    th.start()
    time.sleep(3)                                                              # la recherche est finie (< 1 s), la génération (~20 s) est en cours
    t0 = time.time()
    h = requests.get(T.url + "/api/health", timeout=5)
    st = requests.get(T.url + "/api/status", timeout=5).json()
    lat = time.time() - t0
    second = requests.post(T.url + "/api/chat", json={"question": Q_REAL}, timeout=10)
    th.join(300)
    assert h.status_code == 200 and lat < 3, lat
    assert st["llm"]["online"] is True and st["app"]["state"] == "ready", st
    assert second.status_code == 429 and second.json()["error"]["code"] == "busy", second.text[:200]
    assert box["r"].status_code == 200 and box["r"].json()["status"] == "answered"


def test_log_has_durations_and_no_question_text_and_access_log_has_no_body():
    log = (T.runtime / "api.log").read_text(encoding="utf-8")
    recs = [json.loads(x) for x in log.splitlines() if x.strip().startswith("{")]
    chats = [x for x in recs if x["event"] == "chat" and x.get("question_chars") == len(Q_REAL)]
    assert chats, "aucun enregistrement de la question réelle"
    c = chats[0]
    assert c["status"] == "answered" and c["sources"] >= 1 and c["retriever"] == "hybrid_rerank" and c["rerank_ms"] > 0 and c["generation_ms"] > 1000 and c["total_ms"] > 1000 and "ts" in c
    assert "question" not in c and "plafond" not in log.lower() and "déposant" not in log.lower(), "le texte des questions ne doit pas être journalisé par défaut"
    access = (T.runtime / "access.log").read_text(encoding="utf-8")
    assert "POST /api/chat" in access and "plafond" not in access.lower()


def test_remote_llm_stays_disabled_even_when_the_environment_asks_for_it():
    other = Target(env_extra={"AGENT_LLM": "anthropic", "AGENT_ALLOW_REMOTE_LLM": "1", "ANTHROPIC_API_KEY": "FAKE-KEY-FOR-TEST-NOT-REAL", "AGENT_MODEL": "x"})
    try:
        st = other.wait_ready()
        assert st["remote_llm"] is False and st["llm"]["provider"] == "local" and st["llm"]["local_only"] is True
        assert "FAKE-KEY" not in json.dumps(st)
        log = (other.runtime / "api.log").read_text(encoding="utf-8")
        assert "env_neutralised" in log and "FAKE-KEY" not in log
    finally:
        other.stop()


def test_application_refuses_to_start_when_the_frozen_engine_would_be_modified():
    env = dict(os.environ, AGENT_RR_MIN="0", LOCAL_APP_PORT=str(free_port()), LOCAL_APP_RUNTIME=tempfile.mkdtemp(prefix="local_app_it_"), PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "-m", "local_app"], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode != 0 and "AGENT_RR_MIN" in (r.stderr + r.stdout) and "système gelé" in (r.stderr + r.stdout)
    env = dict(os.environ, AGENT_LOCAL_URL="http://example.com:8187", LOCAL_APP_PORT=str(free_port()), LOCAL_APP_RUNTIME=tempfile.mkdtemp(prefix="local_app_it_"), PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, "-m", "local_app"], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert r.returncode != 0 and "machine locale" in (r.stderr + r.stdout)


def run_browser_end_to_end():
    """Interface -> ... -> réponse affichée, dans un vrai navigateur (2 tests Node). Retourne (réussis, total)."""
    node = subprocess.run(["where", "node"], capture_output=True, text=True).stdout.split("\n")[0].strip() or "node"
    env = dict(os.environ, UI_URL_REAL=T.url + "/")
    r = subprocess.run([node, "--test", "--test-timeout=400000", "--test-reporter=spec", str(ROOT / "local_app" / "tests" / "test_ui_real.mjs")], env=env, cwd=ROOT,
                       capture_output=True, text=True, encoding="utf-8", timeout=900)
    out = r.stdout + r.stderr
    print(out)
    m1, m2 = re.search(r"ℹ pass (\d+)", out), re.search(r"ℹ tests (\d+)", out)
    return (int(m1.group(1)) if m1 else 0), (int(m2.group(1)) if m2 else 2)


TESTS = [(n, f) for n, f in sorted(globals().items(), key=lambda kv: kv[1].__code__.co_firstlineno if callable(kv[1]) and hasattr(kv[1], "__code__") else 0) if n.startswith("test_")]

if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    T = Target()
    passed = total = 0
    try:
        for name, fn in TESTS:
            total += 1
            try:
                fn()
                passed += 1
                print("ok     ", name)
            except Exception:
                print("ECHEC  ", name)
                traceback.print_exc()
        ok, n = run_browser_end_to_end()
        passed, total = passed + ok, total + n
    finally:
        T.stop()
    real = RESULTS.get("real")
    if real:
        print(f"\nQuestion réelle : {RESULTS['real_wall_s']:.1f} s (API {real['durations_ms']['api']} ms, recherche {real['durations_ms']['retrieval']} ms, "
              f"reranking {real['durations_ms']['reranking']} ms, génération {real['durations_ms']['generation']} ms) ; connexions observées : {sorted(RESULTS['peers'])}")
    print(f"\nTests intégration : {passed}/{total}")
    sys.exit(0 if passed == total else 1)
