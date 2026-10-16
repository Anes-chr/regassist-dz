"""Tests de l'API locale (couche de phase 6) avec un FAUX agent : routes, validation, états, sécurité. Aucun modèle n'est chargé.
Lancer : python local_app/tests/test_api.py   (affiche « Tests API : X/Y »)."""
import json
import os
import re
import sys
import tempfile
import threading
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from local_app import config as C                      # noqa: E402
from local_app import service as S                     # noqa: E402
from local_app.server import create_app               # noqa: E402
from local_app.tests import fakes                      # noqa: E402

PORT = 8799
BASE = f"http://127.0.0.1:{PORT}"
WIN_PATH = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/]")                 # « D:\… » (pas « https://… »)
os.environ["AGENT_LLM"] = "local"


def build(agent=None, probe=None, warm=True, debug=False):
    state = {"online": True}
    agent = agent or fakes.make_agent(state=state)
    probe = probe or (lambda: {"online": state["online"], "model": "qwen3-4b-instruct-2507-q4_k_m", "model_matches": True})
    svc = S.Service(agent=agent, llm_probe=probe, debug=debug)
    if warm:
        svc.warm_up()
    app = create_app(svc, PORT)
    return svc, app.test_client(), agent, state


def post(client, body, **kw):
    return client.post("/api/chat", json=body, base_url=BASE, **kw)


def get(client, path, **kw):
    return client.get(path, base_url=BASE, **kw)


def test_health():
    _, c, _, _ = build()
    r = get(c, "/api/health")
    assert r.status_code == 200 and r.get_json() == {"status": "ok"}


def test_status_reports_real_checks_and_exposes_no_path():
    svc, c, _, state = build()
    d = get(c, "/api/status").get_json()
    assert d["phase"] == "PHASE_4_FROZEN" and d["status"] == "NO-GO PROVISOIRE", d["phase"]            # lus dans le manifeste et le marqueur, pas écrits en dur
    assert d["status_reasons"] == ["validation humaine absente", "TEST v2 absent"]
    assert d["agent"]["ready"] and d["retrieval"]["ready"] and d["reranker"]["ready"] and d["app"]["state"] == "ready"
    assert d["llm"]["online"] is True and d["llm"]["local_only"] is True
    assert d["remote_llm"] is False and d["ocr_experimental"] is False and d["ocr_uncertain_active"] is True
    assert not WIN_PATH.search(json.dumps(d)), "chemin Windows exposé"
    state["online"] = False
    svc._llm_cache = (0.0, None)
    d = get(c, "/api/status").get_json()
    assert d["llm"]["online"] is False and d["llm"]["message"] == C.LLM_UNAVAILABLE_MESSAGE


def test_status_is_starting_before_warmup_and_never_claims_ready():
    svc, c, _, _ = build(warm=False)
    d = get(c, "/api/status").get_json()
    assert d["app"]["state"] == "starting" and not d["retrieval"]["ready"] and not d["reranker"]["ready"] and not d["agent"]["ready"]


def test_status_degraded_when_the_engine_fell_back_to_legacy():
    agent = fakes.make_agent(fallback="FileNotFoundError: x")
    svc, c, _, _ = build(agent=agent)
    d = get(c, "/api/status").get_json()
    assert d["app"]["state"] == "degraded" and d["retrieval"]["fallback"] is True and not d["reranker"]["ready"], d


def test_status_error_when_warmup_fails():
    agent = fakes.make_agent()
    agent.search = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    svc, c, _, _ = build(agent=agent)
    d = get(c, "/api/status").get_json()
    assert d["app"]["state"] == "error" and d["agent"]["ready"] is False and d["retrieval"]["ready"] is False


def test_chat_answer_with_sources_forwards_the_question_unchanged_to_the_existing_pipeline():
    svc, c, agent, _ = build()
    q = "Quel est le plafond d'indemnisation par déposant ?"
    r = post(c, {"question": "  " + q + "  "})
    assert r.status_code == 200, r.get_data(as_text=True)
    assert agent.calls == [(q, True, 6)], agent.calls                                  # même appel que l'interface existante : ask(q, use_llm=True), k par défaut
    d = r.get_json()
    assert d["status"] == "answered" and d["found"] is True and d["mode"] == "llm" and d["retriever"] == "hybrid_rerank"
    assert "2.000.000 DA" in d["answer"] and len(d["sources"]) == 2 and [x["id"] for x in d["citations"]] == ["S1"]
    s = d["sources"][0]
    for k in ("id", "chunk_id", "texte", "titre", "article", "emplacement", "page", "document_url", "source_url", "statut", "statut_juridique", "statut_detail", "extrait", "date", "relations"):
        assert k in s, k
    assert s["type"] == "règlement" and s["document_url"].startswith("https://")
    assert d["llm"] == {"requested": True, "available": True, "message": None}


def test_internal_fields_are_never_exposed():
    _, c, _, _ = build()
    raw = post(c, {"question": "plafond"}).get_data(as_text=True)
    for forbidden in ("score", "similarite", "rerank_best", "relations_prompt", "statut_regle", "all_retrieved", "llm_timings", "ocr_uncertain_tokens"):
        assert forbidden not in raw, forbidden
    d = json.loads(raw)
    assert "rerank_best" not in d["timings"] and not WIN_PATH.search(raw)


def test_debug_mode_adds_internal_fields_only_when_enabled():
    _, c, _, _ = build(debug=True)
    d = post(c, {"question": "plafond"}).get_json()
    assert d["sources"][0]["score"] == 0.93 and d["debug"]["rerank_best"] == 2.7


def test_durations_are_measured_for_api_pipeline_retrieval_reranking_generation():
    _, c, _, _ = build()
    d = post(c, {"question": "plafond"}).get_json()["durations_ms"]
    assert set(d) == {"api", "pipeline", "retrieval", "reranking", "generation"}
    assert d["reranking"] == 444.1 and d["generation"] == 20100 and d["retrieval"] == round(454.4 - 444.1, 1)
    assert d["api"] >= d["pipeline"] >= 0


def test_empty_question():
    _, c, agent, _ = build()
    for body in ({"question": ""}, {"question": "   \n\t "}):
        r = post(c, body)
        assert r.status_code == 400 and r.get_json()["error"]["code"] == "empty_question"
    assert agent.calls == []


def test_missing_wrong_type_unknown_field_and_short_question():
    _, c, agent, _ = build()
    assert post(c, {}).get_json()["error"]["code"] == "invalid_request"
    assert post(c, {"question": 42}).status_code == 400
    assert post(c, ["question"]).status_code == 400
    r = post(c, {"question": "plafond", "llm": False})
    assert r.status_code == 400 and "llm" in r.get_json()["error"]["message"]
    assert post(c, {"question": "ab"}).get_json()["error"]["code"] == "question_too_short"
    assert post(c, {"question": "bonjour\x00monde"}).get_json()["error"]["code"] == "invalid_question"
    assert agent.calls == []


def test_question_too_long():
    _, c, agent, _ = build()
    assert post(c, {"question": "a" * C.MAX_QUESTION_CHARS}).status_code == 200
    r = post(c, {"question": "a" * (C.MAX_QUESTION_CHARS + 1)})
    assert r.status_code == 422 and r.get_json()["error"]["code"] == "question_too_long"
    assert len(agent.calls) == 1                                                       # la question trop longue n'atteint jamais l'agent


def test_invalid_json_wrong_content_type_and_oversized_body():
    _, c, _, _ = build()
    assert c.post("/api/chat", data="{pas du json", content_type="application/json", base_url=BASE).get_json()["error"]["code"] == "invalid_json"
    assert c.post("/api/chat", data='{"question":"plafond"}', content_type="text/plain", base_url=BASE).status_code == 415
    r = c.post("/api/chat", data='{"question":"' + "a" * 20000 + '"}', content_type="application/json", base_url=BASE)
    assert r.status_code == 413 and r.get_json()["error"]["code"] == "payload_too_large"


def test_llm_generation_failure_while_the_server_is_up_is_not_reported_as_an_offline_model_and_not_duplicated():
    _, c, _, state = build()
    d = post(c, {"question": "ILLISIBLE plafond"}).get_json()               # sonde en ligne, mais la sortie du modèle n'a pas pu être lue
    assert d["status"] == "llm_unavailable" and d["llm"]["available"] is False and d["mode"] == "extractif"
    msg = d["llm"]["message"]
    assert msg.startswith("La réponse n'a pas pu être rédigée correctement") and "plus précise" in msg and "indisponible" not in msg
    assert d["notes"].count(msg) == 1, d["notes"]                          # le message d'échec n'apparaît qu'UNE fois
    assert d["notes"] == ["Correspondance partielle : vérifiez que ces passages répondent bien à votre question.", msg], d["notes"]
    assert "illisible" not in json.dumps(d, ensure_ascii=False) and "réponse extractive" not in json.dumps(d, ensure_ascii=False)


def test_no_direct_answer_lists_and_describes_the_texts_from_metadata_only():
    _, c, _, _ = build()
    d = post(c, {"question": "ILLISIBLE plafond"}).get_json()
    assert d["texts_intro"] == "Je ne peux pas répondre directement, mais voici quelques textes qui pourraient vous aider à trouver la réponse :"
    assert len(d["texts"]) == 1
    x = d["texts"][0]
    assert x["reference"] == "Règlement n° 2020-03 du 15 mars 2020" and x["titre"].startswith("Règlement n°2020-03 du 15 mars 2020 relatif au système de garantie")
    assert x["type"] == "règlement" and x["date"] == "2020-03-15" and x["statut_juridique"] == "ACTIVE" and x["relations"] == {"Abroge": ["Règlement n° 2004-03 du 4 mars 2004"]}
    assert x["passages"] == [{"id": "S1", "emplacement": "Article 10", "page": 3}] and x["document_url"].startswith("https://www.bank-of-algeria.dz/")
    raw = json.dumps(d["texts"], ensure_ascii=False)
    for forbidden in ("score", "similarite", "chunk_id", "extrait", "relations_prompt"):
        assert forbidden not in raw, forbidden                                  # description = métadonnées publiques seulement, pas d'extrait ni de donnée interne


def test_texts_are_grouped_by_document_in_search_order():
    _, c, _, _ = build()
    d = post(c, {"question": "GROUPES"}).get_json()
    t = d["texts"]
    assert [x["reference"] for x in t] == ["Règlement n° 2020-03 du 15 mars 2020", "Instruction n° 05-2025 du 17 juillet 2025"]
    assert [p["id"] for p in t[0]["passages"]] == ["S1", "S2"] and [p["emplacement"] for p in t[0]["passages"]] == ["Article 10", "Article 11"]
    assert t[1]["statut_juridique"] == "ABROGATED" and t[1]["alerte"].startswith("Ce texte a été abrogé par Instruction n° 07-2026") and t[1]["relations"] == {"Abrogé par": ["Instruction n° 07-2026 du 13 juillet 2026"]}
    assert len(d["sources"]) == 3                                              # les passages restent tous disponibles pour l'affichage détaillé


def test_texts_are_offered_whenever_there_is_no_direct_answer_but_sources_exist():
    _, c, _, state = build()
    refmod = post(c, {"question": "REFMODELE"}).get_json()                       # le modèle a refusé de répondre à partir des passages
    assert refmod["status"] == "refused" and len(refmod["texts"]) == 1 and refmod["texts_intro"]
    state["online"] = False
    off = post(c, {"question": "LLMOFF plafond"}).get_json()                     # llama-server éteint
    assert off["status"] == "llm_unavailable" and len(off["texts"]) == 1 and off["texts_intro"]
    state["online"] = True


def test_no_texts_when_there_is_nothing_to_offer_or_a_real_answer_exists():
    _, c, _, _ = build()
    for q, status in (("REFUS capitale", "refused"), ("AMBIGU règlement", "clarification"), ("plafond", "answered")):
        d = post(c, {"question": q}).get_json()
        assert d["status"] == status and d["texts"] == [] and d["texts_intro"] is None, (q, d["texts"])


def test_related_texts_handles_missing_metadata():
    out = S.related_texts([{"id": "S1"}, {"id": "S2", "texte": "Note n° 3", "titre": None, "document_url": None}, {"id": "S3", "texte": "Note n° 3"}])
    assert [x["reference"] for x in out] == [None, "Note n° 3"] and [p["id"] for p in out[1]["passages"]] == ["S2", "S3"] and out[0]["relations"] == {} and S.related_texts([]) == []


def test_server_dying_between_the_probe_and_the_call_reports_the_local_model_message_once():
    _, c, _, state = build()
    d = post(c, {"question": "LLMOFF plafond"}).get_json()                  # sonde en ligne, puis l'agent constate que llama-server ne répond plus
    assert d["status"] == "llm_unavailable" and d["llm"]["message"] == C.LLM_UNAVAILABLE_PUBLIC
    assert d["notes"].count(C.LLM_UNAVAILABLE_PUBLIC) == 1, d["notes"]


def test_generic_failure_message_is_used_when_the_agent_gives_no_specific_note():
    agent = fakes.make_agent()
    base = agent.ask
    def ask(question, use_llm=False, k=6):
        out = base("LLMOFF", use_llm, k)
        out["notes"] = []                                                  # extractif + found sans aucune note de l'agent
        return out
    agent.ask = ask
    _, c, _, _ = build(agent=agent)
    d = post(c, {"question": "plafond"}).get_json()
    assert d["status"] == "llm_unavailable" and d["llm"]["message"] == S.GENERATION_FAILED_MESSAGE and d["notes"] == [S.GENERATION_FAILED_MESSAGE]


TECH_WORDS = re.compile(r"llama|LLM|rerank|hybride|modèle local|OCR_UNCERTAIN|\[règle|llm_local|qwen|8187|PHASE_4|NO-GO", re.I)


def test_no_technical_vocabulary_in_any_user_facing_text():
    """Notes, messages et introduction destinés à l'utilisateur : ni LLM, ni llama-server, ni reranker, ni règle interne, ni OCR_UNCERTAIN, ni port, ni phase de gel."""
    _, c, _, state = build()
    state["online"] = False
    for q in ("ILLISIBLE plafond", "LLMOFF plafond", "REFMODELE", "REPLI plafond", "CODES plafond", "GROUPES", "TITRE", "plafond", "REFUS capitale", "AMBIGU règlement"):
        d = post(c, {"question": q}).get_json()
        shown = json.dumps({"notes": d["notes"], "message": d["llm"]["message"], "intro": d["texts_intro"], "disclaimer": d["disclaimer"]}, ensure_ascii=False)
        assert not TECH_WORDS.search(shown), (q, TECH_WORDS.search(shown).group(0), shown)
    state["online"] = True


def test_internal_wording_of_the_agent_notes_is_translated_to_plain_language():
    out = S.clean_notes(["[S1] Statut de vigueur non déterminé (aucune relation ni période dans le corpus) : ne pas présenter comme applicable [règle U-ISOL, confiance LOW].",
                         "Version remplacée par un texte plus récent, écartée du contexte du LLM : Instruction n° 05-2025 du 17 juillet 2025, Article 9.",
                         "[S2] OCR_UNCERTAIN : valeur numérique de ce passage arabe non corroborée par le texte français (2000.000).",
                         "Réponse du modèle normalisée en refus : il indiquait lui-même que l'information n'est pas dans les sources."])
    assert out[0] == "[S1] Statut de vigueur non déterminé (aucune relation ni période dans le corpus) : ne pas présenter comme applicable."
    assert out[1] == "Version remplacée par un texte plus récent, écartée de l'analyse : Instruction n° 05-2025 du 17 juillet 2025, Article 9."
    assert out[2].startswith("[S2] À vérifier : valeur numérique de ce passage arabe") and "(2000.000)" in out[2]          # la valeur douteuse reste signalée telle quelle
    assert out[3] == "La réponse a été ramenée à un refus : l'information demandée ne figure pas dans les sources."


def test_llm_unavailable_shows_the_required_message_and_hides_internal_details():
    _, c, _, state = build()
    state["online"] = False                                                 # llama-server éteint : la sonde du démarrage de la requête échoue
    r = post(c, {"question": "LLMOFF plafond"})
    d = r.get_json()
    assert r.status_code == 200 and d["status"] == "llm_unavailable" and d["mode"] == "extractif"
    assert d["llm"]["available"] is False and d["llm"]["message"] == "Le service de rédaction des réponses est momentanément indisponible."
    raw = json.dumps(d, ensure_ascii=False)
    assert "start_server" not in raw and "llm_local" not in raw and "8187" not in raw and "llama-server" not in raw      # le message d'administration n'est jamais envoyé à l'utilisateur
    assert d["notes"][0] == d["llm"]["message"] and len(d["sources"]) == 1


def test_agent_unavailable_returns_503_without_path_or_exception_text():
    _, c, _, _ = build()
    r = post(c, {"question": "PLANTAGE"})
    raw = r.get_data(as_text=True)
    assert r.status_code == 503 and r.get_json()["error"]["code"] == "agent_unavailable"
    assert "vec_df4dd" not in raw and "FileNotFound" not in raw and not WIN_PATH.search(raw)


def test_unexpected_error_returns_500_without_stack_trace_and_the_service_keeps_working():
    _, c, _, _ = build()
    r = post(c, {"question": "BUG"})
    raw = r.get_data(as_text=True)
    assert r.status_code == 500 and r.get_json()["error"]["code"] == "internal_error"
    assert "Traceback" not in raw and "secret" not in raw and "ValueError" not in raw
    assert post(c, {"question": "plafond"}).status_code == 200


def test_refusal_is_displayed_as_a_refusal_not_as_an_answer():
    _, c, _, _ = build()
    d = post(c, {"question": "REFUS capitale"}).get_json()
    assert d["status"] == "refused" and d["found"] is False and d["answer"] == fakes.NOT_FOUND and d["sources"] == [] and d["citations"] == []


def test_model_refusal_keeps_the_examined_sources_but_cites_none():
    _, c, _, _ = build()
    d = post(c, {"question": "REFMODELE"}).get_json()
    assert d["status"] == "refused" and d["reason"] == "refus_modele" and len(d["sources"]) == 1 and d["citations"] == []


def test_ambiguous_question_is_flagged():
    _, c, _, _ = build()
    d = post(c, {"question": "AMBIGU règlement"}).get_json()
    assert d["status"] == "clarification" and d["clarify"] is True and d["found"] is False and "trop générale" in d["answer"]


def test_fallback_engine_note_is_rewritten_without_path():
    _, c, _, _ = build()
    d = post(c, {"question": "REPLI plafond"}).get_json()
    raw = json.dumps(d, ensure_ascii=False)
    assert d["retriever"] == "legacy" and "moins fiables" in d["notes"][0] and "vec_df4dd" not in raw and not WIN_PATH.search(raw)


def test_busy_service_rejects_a_second_question_instead_of_running_two_pipelines():
    svc, c, agent, _ = build()
    assert svc._lock.acquire(blocking=False)
    try:
        r = post(c, {"question": "plafond"})
        assert r.status_code == 429 and r.get_json()["error"]["code"] == "busy" and agent.calls == []
    finally:
        svc._lock.release()
    assert post(c, {"question": "plafond"}).status_code == 200


def test_questions_are_refused_while_the_engine_is_loading():
    _, c, agent, _ = build(warm=False)
    r = post(c, {"question": "plafond"})
    assert r.status_code == 503 and r.get_json()["error"]["code"] == "warming_up" and agent.calls == []


def test_host_and_origin_guards_block_dns_rebinding_and_cross_site_requests():
    _, c, agent, _ = build()
    assert c.get("/api/status", base_url="http://evil.example:8799").status_code == 403
    assert c.get("/api/status", base_url="http://127.0.0.1:3000").status_code == 403                   # autre port, même machine (ex. un autre service local)
    assert get(c, "/api/status", headers={"Origin": "http://localhost:3000"}).status_code == 403
    assert get(c, "/api/status", headers={"Origin": "https://evil.example"}).status_code == 403
    assert post(c, {"question": "plafond"}, headers={"Origin": "http://evil.example"}).status_code == 403
    assert get(c, "/api/status", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert get(c, "/api/status", headers={"Origin": BASE, "Sec-Fetch-Site": "same-origin"}).status_code == 200
    assert c.get("/api/status", base_url=f"http://localhost:{PORT}").status_code == 200
    assert agent.calls == []


def test_no_cors_headers_are_ever_emitted_and_security_headers_are_present():
    _, c, _, _ = build()
    for r in (get(c, "/api/status", headers={"Origin": BASE}), get(c, "/api/health"), get(c, "/"), get(c, "/app.js"), get(c, "/inconnu"),
              get(c, "/api/status", headers={"Origin": "https://evil.example"})):
        assert not [h for h in r.headers.keys() if h.lower().startswith("access-control-")], r.headers
        csp = r.headers["Content-Security-Policy"]
        assert "default-src 'none'" in csp and "connect-src 'self'" in csp and "script-src 'self'" in csp and "http" not in csp and "unsafe" not in csp
        assert r.headers["X-Content-Type-Options"] == "nosniff" and r.headers["X-Frame-Options"] == "DENY" and r.headers["Referrer-Policy"] == "no-referrer"
    assert get(c, "/api/status").headers["Cache-Control"] == "no-store"
    assert c.options("/api/chat", base_url=BASE, headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"}).status_code in (403, 405)


def test_static_interface_is_served_and_unknown_paths_do_not_leak_files():
    _, c, _, _ = build()
    html = get(c, "/").get_data(as_text=True)
    assert "ASSISTANT JURIDIQUE" in html and 'src="app.js"' in html
    assert get(c, "/app.js").status_code == 200 and get(c, "/app.css").status_code == 200 and get(c, "/favicon.ico").status_code == 204
    for p in ("/service.py", "/../config.py", "/..%2fconfig.py", "/runtime/api.log", "/tests/fakes.py", "/api/inconnu", "/static/app.js"):
        r = get(c, p)
        assert r.status_code in (404, 403) and r.is_json, (p, r.status_code)
    assert post(c, {"question": "x"}).status_code == 400 and c.delete("/api/chat", base_url=BASE).status_code == 405


def test_static_files_load_nothing_from_outside_the_application():
    html = (C.STATIC_DIR / "index.html").read_text(encoding="utf-8")
    css = (C.STATIC_DIR / "app.css").read_text(encoding="utf-8")
    js = (C.STATIC_DIR / "app.js").read_text(encoding="utf-8")
    assert not re.search(r"""(?:src|href)\s*=\s*["'](?:https?:)?//""", html), "ressource externe dans le HTML"
    assert not re.search(r"url\(\s*[\"']?(?:https?:)?//|@import", css), "ressource externe dans le CSS"
    assert "<style" not in html and not re.search(r"\sstyle\s*=", html) and not re.search(r"\son[a-z]+\s*=", html)   # compatible CSP : pas de style ni de script en ligne
    assert "innerHTML" not in js and "eval(" not in js and "document.write" not in js and "insertAdjacentHTML" not in js
    for m in re.finditer(r"fetch\(\s*([^,)]+)", js):
        assert m.group(1).strip().startswith(("'/api/", '"/api/')), m.group(1)           # seuls appels réseau : l'API de la même origine
    assert "XMLHttpRequest" not in js and "WebSocket" not in js and "sendBeacon" not in js and "import(" not in js
    everything = html + css + js + (C.STATIC_DIR / "favicon.svg").read_text(encoding="utf-8")
    assert not re.search(r"sk-[A-Za-z0-9_-]{8,}|ANTHROPIC|api[_-]?key|secret|token", everything, re.I), "clé, jeton ou secret dans l'interface"
    assert not re.search("[\U0001F000-\U0001FAFF☀-➿️]", everything), "emoji dans l'interface"
    literals = re.findall(r"'(?:[^'\\\n]|\\.)*'|\"(?:[^\"\\\n]|\\.)*\"", js)                      # chaînes du JavaScript (pas ses identifiants : r.llm, ocr_uncertain…)
    visible = html + " ".join(literals)
    assert not re.search(r"llama|qwen|rerank|hybrid|PHASE_4|NO-GO|127\.0\.0\.1|OCR_UNCERTAIN|chunk|Traçabilité|\bLLM\b|\bport\b|\bms\b", visible, re.I), \
        "détail technique dans l'interface : " + re.search(r"llama|qwen|rerank|hybrid|PHASE_4|NO-GO|127\.0\.0\.1|OCR_UNCERTAIN|chunk|Traçabilité|\bLLM\b|\bport\b|\bms\b", visible, re.I).group(0)
    assert "non officiel" in html and "intelligence artificielle" in html and "publics" in html          # mention claire : projet éducatif non officiel, données publiques, IA


def test_notes_are_cleaned_of_paths_scripts_and_exception_names():
    out = S.clean_notes(["Voir D:\\llm\\models\\x.gguf et C:/Users/a/b.txt ici", "lancez llm_local\\start_server.ps1 puis relancez", "ok", "ok"])
    assert out[0] == "Voir [chemin masqué] et [chemin masqué] ici" and "[chemin masqué]" in out[1] and "start_server" not in out[1] and out.count("ok") == 1
    assert S.clean_notes(["Source : https://www.bank-of-algeria.dz/stoodroa/x.pdf"]) == ["Source : https://www.bank-of-algeria.dz/stoodroa/x.pdf"]    # une URL n'est pas un chemin


def test_environment_guard_forces_local_llm_and_refuses_behaviour_changing_variables():
    env = {"AGENT_LLM": "anthropic", "AGENT_ALLOW_REMOTE_LLM": "1", "ANTHROPIC_API_KEY": "sk-test-xxx", "AGENT_MODEL": "m"}
    rep = S.check_environment(env)
    assert env["AGENT_LLM"] == "local" and "AGENT_ALLOW_REMOTE_LLM" not in env and "ANTHROPIC_API_KEY" not in env and "AGENT_MODEL" not in env
    assert set(rep["neutralised"]) == {"AGENT_LLM", "AGENT_ALLOW_REMOTE_LLM", "ANTHROPIC_API_KEY", "AGENT_MODEL"}
    assert "sk-test" not in json.dumps(rep)
    for bad in ("AGENT_RR_MIN", "AGENT_W_RERANK", "AGENT_RERANK_N", "AGENT_LANGS", "AGENT_JSON_SCHEMA"):
        try:
            S.check_environment({bad: "0"})
        except SystemExit as e:
            assert bad in str(e)
        else:
            raise AssertionError(bad)
    try:
        S.check_environment({"AGENT_RETRIEVER": "bm25"})
    except SystemExit:
        pass
    else:
        raise AssertionError("AGENT_RETRIEVER=bm25 doit être refusé")
    assert S.check_environment({"AGENT_RETRIEVER": "auto"})["engine_overrides"] == []
    assert S.check_environment({"AGENT_RR_MIN": "0", "LOCAL_APP_ALLOW_ENV_OVERRIDES": "1"})["engine_overrides"] == ["AGENT_RR_MIN"]
    for url in ("http://example.com:8187", "http://192.168.1.5:8187", "https://api.anthropic.com"):
        try:
            S.check_environment({"AGENT_LOCAL_URL": url})
        except SystemExit as e:
            assert "machine locale" in str(e)
        else:
            raise AssertionError(url)
    assert S.check_environment({"AGENT_LOCAL_URL": "http://localhost:8187"}) and S.check_environment({"AGENT_LOCAL_URL": "http://[::1]:8187"})


def test_log_records_durations_but_not_the_question_text_by_default():
    d = Path(tempfile.mkdtemp(prefix="local_app_log_"))
    S.setup_logging(d / "api.log")
    os.environ.pop("LOCAL_APP_LOG_QUESTIONS", None)
    _, c, _, _ = build()
    secret = "question confidentielle sur le plafond XYZ123"
    assert post(c, {"question": secret}).status_code == 200
    for h in list(S.LOG.handlers):
        h.flush()
    lines = [json.loads(x) for x in (d / "api.log").read_text(encoding="utf-8").splitlines() if x.strip()]
    rec = [x for x in lines if x["event"] == "chat"][-1]
    assert "XYZ123" not in (d / "api.log").read_text(encoding="utf-8") and "question" not in rec and rec["question_chars"] == len(secret)
    assert rec["status"] == "answered" and rec["sources"] == 2 and rec["retrieval_ms"] == 454.4 and rec["rerank_ms"] == 444.1 and rec["generation_ms"] == 20100 and rec["total_ms"] >= 0 and "ts" in rec
    os.environ["LOCAL_APP_LOG_QUESTIONS"] = "1"
    try:
        post(c, {"question": secret})
        for h in list(S.LOG.handlers):
            h.flush()
        assert secret in (d / "api.log").read_text(encoding="utf-8")                      # uniquement sur demande explicite
    finally:
        os.environ.pop("LOCAL_APP_LOG_QUESTIONS", None)
        for h in list(S.LOG.handlers):
            S.LOG.removeHandler(h)
            h.close()


def test_errors_are_logged_without_stack_trace_unless_debug():
    d = Path(tempfile.mkdtemp(prefix="local_app_log_"))
    S.setup_logging(d / "api.log")
    _, c, _, _ = build()
    post(c, {"question": "BUG"})
    for h in list(S.LOG.handlers):
        h.flush()
    txt = (d / "api.log").read_text(encoding="utf-8")
    assert "chat_error" in txt and "Traceback" not in txt and "secret.txt" not in txt
    for h in list(S.LOG.handlers):
        S.LOG.removeHandler(h)
        h.close()


def test_concurrent_status_and_health_answer_while_a_question_is_running():
    state = {"online": True}
    agent = fakes.make_agent(delay=0.8, state=state)
    svc, c, _, _ = build(agent=agent)
    t = threading.Thread(target=lambda: post(c, {"question": "plafond"}))
    t.start()
    import time
    time.sleep(0.2)
    assert get(c, "/api/health").status_code == 200 and get(c, "/api/status").status_code == 200
    assert post(c, {"question": "plafond"}).status_code == 429
    t.join()


def test_retry_after_header_present_on_http_429():
    state = {"online": True}
    agent = fakes.make_agent(delay=0.8, state=state)
    svc, c, _, _ = build(agent=agent)
    t = threading.Thread(target=lambda: post(c, {"question": "plafond"}))
    t.start()
    import time
    time.sleep(0.2)
    busy_resp = post(c, {"question": "plafond"})
    assert busy_resp.status_code == 429
    assert busy_resp.headers.get("Retry-After") == "30", f"Retry-After manquant ou incorrect: {busy_resp.headers}"
    t.join()


def test_production_mode_host_and_origin_allowlist():
    old_mode = os.environ.get("REGASSIST_DEPLOY_MODE")
    old_hosts = os.environ.get("REGASSIST_ALLOWED_HOSTS")
    old_origins = os.environ.get("REGASSIST_ALLOWED_ORIGINS")
    try:
        os.environ["REGASSIST_DEPLOY_MODE"] = "production"
        os.environ["REGASSIST_ALLOWED_HOSTS"] = "regassist.example.com,api.example.com"
        os.environ["REGASSIST_ALLOWED_ORIGINS"] = "https://regassist.example.com"

        _, c, _, _ = build()

        # Rejet de l'hôte loopback par défaut en mode production car non listé
        assert c.get("/api/health", base_url="http://127.0.0.1:8790").status_code == 403
        assert c.get("/api/health", base_url="http://evil.example.com").status_code == 403

        # Hôte approuvé
        assert c.get("/api/health", base_url="https://regassist.example.com").status_code == 200

        # Origine approuvée
        assert c.get("/api/health", base_url="https://regassist.example.com", headers={"Origin": "https://regassist.example.com"}).status_code == 200

        # Origine non approuvée
        assert c.get("/api/health", base_url="https://regassist.example.com", headers={"Origin": "https://malicious.example"}).status_code == 403
        assert c.post("/api/chat", base_url="https://regassist.example.com", json={"question": "plafond"}, headers={"Origin": "https://malicious.example"}).status_code == 403
    finally:
        for k, v in [("REGASSIST_DEPLOY_MODE", old_mode), ("REGASSIST_ALLOWED_HOSTS", old_hosts), ("REGASSIST_ALLOWED_ORIGINS", old_origins)]:
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


TESTS = [(n, f) for n, f in sorted(globals().items(), key=lambda kv: kv[1].__code__.co_firstlineno if callable(kv[1]) and hasattr(kv[1], "__code__") else 0) if n.startswith("test_")]

if __name__ == "__main__":
    failed = []
    for name, fn in TESTS:
        try:
            fn()
            print("ok     ", name)
        except Exception:
            failed.append(name)
            print("ECHEC  ", name)
            traceback.print_exc()
    print(f"\nTests API : {len(TESTS) - len(failed)}/{len(TESTS)}")
    sys.exit(1 if failed else 0)
