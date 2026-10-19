"""Service applicatif : enveloppe en LECTURE SEULE autour du système gelé (PHASE_4_FROZEN).

Rôle : valider la question, appeler `agent_fr.agent.ask(question, use_llm=True)` TELLE QUELLE (mêmes paramètres que l'interface existante), puis
mettre la sortie en forme pour l'interface (retirer ce qui est interne, signaler l'état du LLM, mesurer les durées). Aucune règle juridique,
aucun score, aucun seuil n'est ajouté, modifié ou réinterprété ici : `status` ci-dessous ne fait que NOMMER ce que `found`, `mode`, `clarify`
et `reason` de la sortie de l'agent disent déjà. Seule exception, hors du moteur : les messages de pure courtoisie (« Bonjour », « Merci », « Qui es-tu ? »)
reçoivent une réponse fixe (`status` = « smalltalk », voir smalltalk.py) au lieu d'être traités comme des questions de recherche.
"""
import hashlib
import json
import logging
import logging.handlers
import os
import re
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from . import config as C
from . import grounding
from . import smalltalk

LOG = logging.getLogger("local_app")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_PATH = re.compile(r"(?:(?<![A-Za-z0-9])[A-Za-z]:[\\/][^\s\"'<>|)]*)|(?:\\\\[^\s\"'<>|)]+)|(?:\bllm_local[\\/][^\s\"'<>|)]*)")   # « D:\… » mais pas « https://… »
_LOOPBACK = {"127.0.0.1", "localhost", "::1"}

# Notes internes de l'agent -> message destiné à l'utilisateur (aucun chemin, aucun nom de script, aucun type d'exception).
# Le vocabulaire technique (modèle, LLM, serveur, moteur, reranker, règles internes) n'est jamais montré à l'utilisateur.
_NOTE_RULES = [
    (re.compile(r"llama-server ne répond pas"), C.LLM_UNAVAILABLE_PUBLIC),
    (re.compile(r"Le serveur LLM a refusé ou interrompu"),
     "La réponse n'a pas pu être rédigée : le service de rédaction a interrompu la requête. Les textes retrouvés sont affichés."),
    (re.compile(r"Réponse du modèle illisible"),
     "La réponse n'a pas pu être rédigée correctement (question trop large ou réponse trop longue). Les textes retrouvés sont affichés ; essayez une question plus précise (un texte, un sujet, une période)."),
    (re.compile(r"Moteur de recherche de repli"),
     "La recherche avancée est momentanément indisponible : une recherche simplifiée a été utilisée, ses résultats sont moins fiables."),
    (re.compile(r"API distante refusée|ANTHROPIC_API_KEY"), "Le service de rédaction distant est désactivé."),
    (re.compile(r"Réponse du modèle normalisée en refus"), "La réponse a été ramenée à un refus : l'information demandée ne figure pas dans les sources."),
]
# Remplacements de fragments (le reste de la note est conservé) : jargon interne -> langage courant.
_NOTE_SUBS = [
    (re.compile(r"\s*\[règle [^\]]*\]"), ""),                                    # « [règle U-ISOL, confiance LOW] »
    (re.compile(r"écartée du contexte du LLM"), "écartée de l'analyse"),
    (re.compile(r"OCR_UNCERTAIN : "), "À vérifier : "),
]

# Messages d'échec de la génération (les trois premières règles ci-dessus) : quand l'un d'eux est présent, il EST le message de l'état `llm_unavailable`
# (pas de second message redondant).
_FAILURE_NOTES = {repl for _rx, repl in _NOTE_RULES[:3]}
GENERATION_FAILED_MESSAGE = "La réponse n'a pas pu être rédigée ; seuls les textes retrouvés sont affichés."

# Champs d'une source transmis à l'interface. Les scores internes (score, similarite), la règle interne du statut et le texte de prompt ne le sont pas.
_SOURCE_KEYS = ("id", "chunk_id", "texte", "titre", "article", "emplacement", "chapitre", "section", "page", "page_fin", "document_url", "source_url",
                "statut", "relations", "extraction", "a_verifier", "autres_copies", "extrait", "via", "alerte", "date", "statut_juridique",
                "statut_detail", "statut_confiance", "ocr_uncertain")
_DEBUG_SOURCE_KEYS = ("score", "similarite", "statut_regle")
_TIMING_KEYS = ("embed_question_ms", "search_ms", "rerank_ms", "total_ms")          # `rerank_best` (score interne du reranker) n'est jamais transmis


def related_texts(sources: list) -> list:
    """Regroupe les passages retrouvés par TEXTE du corpus et décrit chaque texte avec ses seules métadonnées : intitulé officiel, type, date, statut juridique calculé
    par le système, relations (modifie / abroge…), articles retrouvés, liens officiels. Rien n'est généré ni interprété (pas de LLM) : une description produite par
    le modèle pourrait inventer, et c'est justement quand il n'a pas pu répondre que cette liste est affichée. Ordre = ordre d'apparition dans la recherche."""
    groups = {}
    for s in sources:
        key = s.get("document_url") or s.get("texte") or s.get("id")
        g = groups.get(key)
        if g is None:
            g = groups[key] = {"reference": s.get("texte"), "titre": s.get("titre"), "type": s.get("type"), "date": s.get("date"), "statut_juridique": s.get("statut_juridique"),
                               "statut_detail": s.get("statut_detail"), "statut": s.get("statut"), "relations": s.get("relations") or {}, "alerte": s.get("alerte"),
                               "document_url": s.get("document_url"), "source_url": s.get("source_url"), "passages": []}
        g["passages"].append({"id": s.get("id"), "emplacement": s.get("emplacement"), "page": s.get("page")})
    return list(groups.values())


class ServiceError(Exception):
    """Erreur destinée à l'utilisateur : code HTTP, code stable, message en français sans détail interne."""

    def __init__(self, http: int, code: str, message: str):
        super().__init__(message)
        self.http, self.code, self.message = http, code, message


def scrub(text) -> str:
    return _PATH.sub("[chemin masqué]", str(text))


def clean_notes(notes) -> list:
    out = []
    for n in notes or []:
        n = str(n)
        for rx, repl in _NOTE_RULES:
            if rx.search(n):
                n = repl
                break
        else:
            for rx, repl in _NOTE_SUBS:
                n = rx.sub(repl, n)
        n = scrub(n)
        if n and n not in out:
            out.append(n)
    return out


def safe_url(u):
    try:
        return u if u and urlparse(u).scheme in ("http", "https") else None
    except ValueError:
        return None


def validate_payload(data) -> str:
    """Valide le corps de POST /api/chat et retourne la question (seulement `strip`ée : le texte n'est pas retouché)."""
    if not isinstance(data, dict):
        raise ServiceError(400, "invalid_request", "Corps JSON attendu : {\"question\": \"...\"}.")
    extra = sorted(set(data) - {"question"})
    if extra:
        raise ServiceError(400, "invalid_request", "Champ(s) non reconnu(s) : " + ", ".join(scrub(str(k))[:40] for k in extra) + ".")
    q = data.get("question")
    if not isinstance(q, str):
        raise ServiceError(400, "invalid_request", "Le champ « question » est obligatoire et doit être du texte.")
    q = q.strip()
    if _CONTROL.search(q):
        raise ServiceError(400, "invalid_question", "La question contient des caractères de contrôle non autorisés.")
    if not q:
        raise ServiceError(400, "empty_question", "La question est vide.")
    if len(q) < C.MIN_QUESTION_CHARS:
        raise ServiceError(400, "question_too_short", f"La question est trop courte (minimum {C.MIN_QUESTION_CHARS} caractères).")
    if len(q) > C.MAX_QUESTION_CHARS:
        raise ServiceError(422, "question_too_long", f"La question dépasse la limite de {C.MAX_QUESTION_CHARS} caractères ({len(q)} saisis).")
    return q


def check_environment(env=None) -> dict:
    """Garde-fous exécutés au démarrage, sur le processus de l'application uniquement (aucun fichier n'est modifié).

    * LLM : toujours LOCAL. Les variables qui activeraient un LLM distant sont retirées de l'environnement du processus ; l'URL du LLM local doit être une adresse de bouclage.
    * Moteur : seules les variables de chemin (AGENT_*_DIR) sont tolérées pour adapter l'arborescence (alors signalées dans /api/status).
      Toute variable modifiant le comportement du moteur gelé (seuil, poids, modèle, moteur de recherche…) entraîne un refus de démarrer.
    """
    env = os.environ if env is None else env
    neutralised = []
    if env.get("AGENT_LLM", "local").lower() not in ("", "local"):
        neutralised.append("AGENT_LLM")
    env["AGENT_LLM"] = "local"
    for name in C.REMOTE_ENV:
        if name in env:
            neutralised.append(name)
            del env[name]
    url = urlparse(env.get("AGENT_LOCAL_URL", "http://127.0.0.1:8187"))
    if (url.hostname or "").lower() not in _LOOPBACK:
        raise SystemExit("AGENT_LOCAL_URL ne désigne pas la machine locale : refus de démarrer (le corpus ne doit pas quitter l'ordinateur).")
    overrides = []
    forbidden = []
    for name in C.ENGINE_ENV:
        val = env.get(name, "")
        if not val:
            continue
        if name == "AGENT_RETRIEVER" and val.lower() in ("auto", "default", "hybrid_rerank"):
            continue                                                          # = moteur par défaut du système gelé
        if name.endswith("_DIR"):
            overrides.append(name)                                            # variable de chemin autorisée (ex. AGENT_VECTOR_DIR)
        else:
            forbidden.append(name)                                            # seuil, poids, modèle ou moteur : strictement refusé
    if forbidden:
        raise SystemExit("Variable(s) d'environnement qui modifient le comportement du système gelé (seuils, poids, modèles) : " + ", ".join(forbidden)
                         + ". Retirez-les (le système PHASE_4_FROZEN ne se configure pas).")
    return {"neutralised": sorted(set(neutralised)), "engine_overrides": overrides}


def setup_logging(path: Path = C.LOG_FILE):
    """Journal local en JSON (une ligne par événement), rotation à 1 Mo x 3. Le texte des questions n'y est écrit que si LOCAL_APP_LOG_QUESTIONS=1."""
    path.parent.mkdir(parents=True, exist_ok=True)
    LOG.setLevel(logging.INFO)
    LOG.propagate = False
    for h in list(LOG.handlers):
        LOG.removeHandler(h)
    h = logging.handlers.RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(message)s"))
    LOG.addHandler(h)
    # Journal d'accès du serveur HTTP (méthode, chemin, code ; jamais le corps des requêtes) dans un fichier tournant, pas sur la console :
    # une console Windows en pause (sélection de texte) bloquerait sinon le serveur à la première écriture.
    acc = logging.getLogger("werkzeug")
    acc.setLevel(logging.INFO)
    acc.propagate = False
    for old in list(acc.handlers):
        acc.removeHandler(old)
    ah = logging.handlers.RotatingFileHandler(path.with_name("access.log"), maxBytes=500_000, backupCount=2, encoding="utf-8")
    ah.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    acc.addHandler(ah)


def probe_llama(timeout: float = 1.5) -> dict:
    """Contrôle réel de llama-server (boucle locale) : /health puis /props (nom du modèle chargé, sans chemin)."""
    from agent_fr import llm_backends as B
    url = B.local_url()
    out = {"online": False, "model": None, "model_matches": None}
    try:
        import requests
        r = requests.get(url + "/health", timeout=timeout)
        out["online"] = r.status_code == 200 and r.json().get("status") == "ok"
    except Exception:
        return out
    if out["online"]:
        try:
            props = requests.get(url + "/props", timeout=timeout).json()
            stem = Path(str(props.get("model_path") or props.get("model_alias") or "").replace("\\", "/")).stem
            if stem:
                out["model"] = stem
                out["model_matches"] = stem.lower() in os.environ.get("AGENT_LOCAL_MODEL_NAME", "qwen3-4b-instruct-2507-q4_k_m (local, CPU)").lower()
        except Exception:
            pass
    return out


class Service:
    def __init__(self, agent=None, llm_probe=None, env_report=None, debug=None, smalltalk_llm=None):
        self._agent_mod = agent
        self._llm_probe = llm_probe or probe_llama
        self._smalltalk_llm = smalltalk_llm or smalltalk.generate            # (question, type) -> texte | None ; les tests injectent un double
        self.env_report = env_report or {"neutralised": [], "engine_overrides": []}
        self.debug = C.debug() if debug is None else debug
        self._lock = threading.Lock()
        self._warm = {"state": "pending", "engine": None, "embed_ok": False, "rerank_ok": False, "error": None, "duration_ms": None,
                      "documents": None, "passages": None}
        self._types = {}
        self._texts = {}                                                         # chunk_id -> texte complet du passage (pour vérifier qu'un terme défini figure dans les sources)
        self._llm_cache = (0.0, None)
        self._freeze_cache = (0.0, None)

    # ----- accès à l'agent gelé (import différé : les tests peuvent injecter un faux agent) -----
    @property
    def agent(self):
        if self._agent_mod is None:
            from agent_fr import agent as a
            self._agent_mod = a
        return self._agent_mod

    # ----- démarrage : vérification RÉELLE de la recherche hybride et du reranker, sans LLM -----
    def warm_up(self):
        with self._lock:
            self._warm["state"] = "running"
            t0 = time.perf_counter()
            try:
                ag = self.agent
                idx = ag.get_index()
                self._types = {c.get("chunk_id"): c.get("document_type") for c in idx.chunks}
                self._texts = {c.get("chunk_id"): c.get("text") for c in idx.chunks if c.get("text")}        # mêmes objets chaîne que l'index : pas de copie
                res = ag.search(idx, C.WARMUP_QUESTION, 3)
                t = getattr(res, "timings", None) or {}
                self._warm.update(documents=len(idx.docs), passages=len(idx.chunks), embed_ok="embed_question_ms" in t, rerank_ok="rerank_ms" in t,
                                  engine=self._engine(), state="done", error=None)
            except Exception as e:                                           # état d'échec explicite ; détail dans le journal local seulement
                self._warm.update(state="error", error=type(e).__name__)
                self.log("warmup_error", error_type=type(e).__name__, error=scrub(e)[:200], trace=traceback.format_exc() if self.debug else None)
            self._warm["duration_ms"] = round((time.perf_counter() - t0) * 1000)
            self.log("warmup", state=self._warm["state"], engine=self._warm["engine"], duration_ms=self._warm["duration_ms"])

    def _engine(self) -> str:
        ag = self.agent
        return "legacy" if (ag.retriever_name() == "legacy" or getattr(ag, "_FALLBACK_REASON", None)) else ag.retriever_name().replace("auto", "hybrid_rerank")

    # ----- journal -----
    def log(self, event: str, **fields):
        rec = {"ts": datetime.now().astimezone().isoformat(timespec="milliseconds"), "event": event}
        rec.update({k: v for k, v in fields.items() if v is not None})
        LOG.info(json.dumps(rec, ensure_ascii=False))

    # ----- /api/status -----
    def _freeze(self) -> dict:
        now = time.time()
        if self._freeze_cache[1] is not None and now - self._freeze_cache[0] < 30:
            return self._freeze_cache[1]
        info = {"phase": None, "status": None, "reasons": [], "created": None, "manifest_sha256": None, "marker_present": C.FREEZE_MARKER.is_file(),
                "ocr_experimental": None, "ocr_uncertain_active": None}
        try:
            raw = C.FREEZE_MANIFEST.read_bytes()
            m = json.loads(raw.decode("utf-8"))
            ocr = (m.get("configuration") or {}).get("ocr") or {}
            cand = str(ocr.get("candidat_experimental", ""))
            info.update(phase=m.get("label") if info["marker_present"] else None, status=m.get("statut_decision"), reasons=list(m.get("raisons_du_statut") or []),
                        created=m.get("cree_le"), manifest_sha256=hashlib.sha256(raw).hexdigest()[:12])
            if cand:
                info["ocr_experimental"] = ("NON DÉPLOYÉ" not in cand.upper()) or ("tessdata_best" in os.environ.get("TESSDATA_PREFIX", "").lower())
            if "OCR_UNCERTAIN" in ocr:
                info["ocr_uncertain_active"] = str(ocr["OCR_UNCERTAIN"]).lower().startswith("actif")
        except (OSError, ValueError):
            pass
        self._freeze_cache = (now, info)
        return info

    def _llm(self) -> dict:
        now = time.time()
        if self._llm_cache[1] is not None and now - self._llm_cache[0] < 3:
            return self._llm_cache[1]
        try:
            p = self._llm_probe()
        except Exception:
            p = {"online": False, "model": None, "model_matches": None}
        self._llm_cache = (now, p)
        return p

    def status(self) -> dict:
        fz, llm, w = self._freeze(), self._llm(), self._warm
        try:
            from agent_fr import llm_backends as B
            provider = B.provider()
        except Exception:
            provider = "local"
        fallback = bool(getattr(self._agent_mod, "_FALLBACK_REASON", None)) if self._agent_mod is not None else False
        engine = "legacy" if fallback else w["engine"]
        warm_done = w["state"] == "done"
        retrieval_ready = warm_done and w["embed_ok"] and not fallback
        reranker_ready = warm_done and w["rerank_ok"] and not fallback
        if w["state"] in ("pending", "running"):
            state = "starting"
        elif w["state"] == "error":
            state = "error"
        else:
            state = "ready" if (retrieval_ready and reranker_ready) else "degraded"
        return {
            "phase": fz["phase"], "status": fz["status"], "status_reasons": fz["reasons"],
            "freeze": {"marker_present": fz["marker_present"], "manifest_sha256": fz["manifest_sha256"], "created": fz["created"]},
            "app": {"state": state, "version": "local_app/1", "engine_overrides": self.env_report["engine_overrides"]},
            "agent": {"ready": warm_done, "error": w["error"]},
            "retrieval": {"ready": retrieval_ready, "engine": engine, "fallback": fallback},
            "reranker": {"ready": reranker_ready, "model": "mmarco-mMiniLMv2-L12-H384 (int8)" if reranker_ready else None},
            "llm": {"online": bool(llm.get("online")), "model": llm.get("model"), "model_matches_expected": llm.get("model_matches"), "provider": provider,
                    "local_only": provider == "local", "message": None if llm.get("online") else C.LLM_UNAVAILABLE_MESSAGE},
            "corpus": {"documents_fr": w["documents"], "passages_fr": w["passages"]},
            "remote_llm": provider != "local",
            "ocr_experimental": fz["ocr_experimental"],
            "ocr_uncertain_active": fz["ocr_uncertain_active"],
            "limits": {"max_question_chars": C.MAX_QUESTION_CHARS},
        }

    # ----- /api/chat -----
    def _smalltalk(self, q: str, st: dict, t_api: float) -> dict:
        """Salutation, remerciement, « qui es-tu » : jamais de recherche. Réponse naturelle du modèle local si la file est libre (il ne voit que ce message de
        courtoisie), sinon — file occupée, modèle éteint ou lent, sortie non conforme — texte fixe immédiat. Une question en cours n'est jamais attendue."""
        reply, source = st["reply"], "fixed"
        if self._warm["state"] not in ("pending", "running") and self._lock.acquire(blocking=False):
            try:
                text = self._smalltalk_llm(q, st)
            except Exception:
                text = None
            finally:
                self._lock.release()
            if text:
                reply, source = text, "llm"
        ms = round((time.perf_counter() - t_api) * 1000)
        self.log("chat", status="smalltalk", kind=st["kind"], source=source, question_chars=len(q), question=q if C.log_questions() else None, sources=0, total_ms=ms)
        return {"question": q, "status": "smalltalk", "found": False, "clarify": False, "mode": "smalltalk", "reason": "smalltalk", "answer": reply,
                "citations": [], "sources": [], "notes": [], "disclaimer": None, "model": None, "provider": None, "retriever": None, "latency_s": None,
                "timings": {}, "durations_ms": {"api": ms, "pipeline": None, "retrieval": None, "reranking": None, "generation": None},
                "llm": {"requested": False, "available": None, "message": None}, "texts": [], "texts_intro": None}

    def chat(self, data) -> dict:
        t_api = time.perf_counter()
        q = validate_payload(data)
        st = smalltalk.classify(q)
        if st is not None:                                                       # message de courtoisie : jamais transmis au moteur gelé (voir smalltalk.py)
            return self._smalltalk(q, st, t_api)
        if self._warm["state"] in ("pending", "running"):
            raise ServiceError(503, "warming_up", "Le service démarre. Réessayez dans quelques secondes.")
        if not self._lock.acquire(blocking=False):
            raise ServiceError(429, "busy", "Une question est déjà en cours de traitement (peut-être celle d'un autre utilisateur). Réessayez dans quelques secondes.")
        status, out, llm_up, n_src, err = "error", {}, False, 0, None
        try:
            llm_up = bool(self._llm_fresh().get("online"))
            t0 = time.perf_counter()
            try:
                out = self.agent.ask(grounding.normalise_question(q), use_llm=True)     # appel inchangé (mêmes paramètres que l'interface existante) ; seules les apostrophes/espaces typographiques sont ramenés à l'ASCII
            except (FileNotFoundError, ImportError, OSError, MemoryError) as e:
                err = type(e).__name__
                raise ServiceError(503, "agent_unavailable", "Le service de recherche est momentanément indisponible. Réessayez dans un instant.") from e
            except Exception as e:
                err = type(e).__name__
                raise ServiceError(500, "internal_error", "Une erreur est survenue. Réessayez dans un instant.") from e
            pipeline_ms = round((time.perf_counter() - t0) * 1000)
            payload = self._ground(q, out, self._shape(q, out, llm_up, pipeline_ms))
            status, n_src = payload["status"], len(payload["sources"])
            self._observe(out)
            payload["durations_ms"]["api"] = round((time.perf_counter() - t_api) * 1000)
            return payload
        except ServiceError as e:
            status = e.code
            if err:
                self.log("chat_error", error_type=err, error=scrub(e.__cause__)[:200], trace=traceback.format_exc() if self.debug else None)
            raise
        finally:
            self._lock.release()
            t = (out.get("timings") or {}) if isinstance(out, dict) else {}
            self.log("chat", status=status, question_chars=len(q), question=q if C.log_questions() else None, sources=n_src, retriever=out.get("retriever") if out else None,
                     embed_ms=t.get("embed_question_ms"), retrieval_ms=t.get("total_ms"), rerank_ms=t.get("rerank_ms"),
                     generation_ms=round(out["latency_s"] * 1000) if out and out.get("mode") == "llm" and out.get("latency_s") is not None else None,
                     total_ms=round((time.perf_counter() - t_api) * 1000), llm_online=llm_up)

    def _ground(self, q: str, out: dict, payload: dict) -> dict:
        """Garde-fou de définition (voir grounding.py) : une réponse rédigée à une question « c'est quoi X ? » est retirée si X ne figure dans aucun des textes retrouvés.
        Ne fait que transformer une réponse en refus ; n'ajoute jamais de contenu juridique."""
        if payload["status"] != "answered":
            return payload
        texts = []
        for c in (out.get("sources") or out.get("citations") or []):
            texts += [c.get("titre"), c.get("extrait"), c.get("texte"), self._texts.get(c.get("chunk_id"))]
        term = grounding.unsupported_term(q, texts)
        if term is None:
            return payload
        self.log("guard", name="terme_absent", term_chars=len(term))
        payload.update(status="refused", found=False, reason="terme_absent", answer=grounding.MESSAGE.format(term=term), citations=[], sources=[], notes=[], texts=[], texts_intro=None)
        return payload

    def _llm_fresh(self) -> dict:
        self._llm_cache = (0.0, None)
        return self._llm()

    def _observe(self, out: dict):
        """Met à jour l'état du moteur avec ce que la dernière question a réellement utilisé (repli éventuel, reranker exécuté)."""
        t = out.get("timings") or {}
        if out.get("retriever"):
            self._warm["engine"] = out["retriever"]
        if "embed_question_ms" in t:
            self._warm["embed_ok"] = True
        if "rerank_ms" in t:
            self._warm["rerank_ok"] = True

    def _public_source(self, c: dict) -> dict:
        s = {k: c.get(k) for k in _SOURCE_KEYS}
        s["type"] = self._types.get(c.get("chunk_id"))
        s["document_url"], s["source_url"] = safe_url(s["document_url"]), safe_url(s["source_url"])
        if self.debug:
            s.update({k: c.get(k) for k in _DEBUG_SOURCE_KEYS})
        return s

    def _shape(self, q: str, out: dict, llm_up: bool, pipeline_ms: int) -> dict:
        mode, found, clarify = out.get("mode"), bool(out.get("found")), bool(out.get("clarify"))
        if clarify:
            status = "clarification"
        elif mode == "llm":
            status = "answered" if found else "refused"
        else:
            status = "llm_unavailable" if found else "refused"                # extractif + found : l'agent n'a pas pu générer (LLM éteint, réponse illisible…)
        raw = out.get("sources") or out.get("citations") or []
        sources = [self._public_source(c) for c in raw]
        cited = [self._public_source(c) for c in (out.get("citations") or [])] if mode == "llm" else []
        notes = clean_notes(out.get("notes"))
        t = {k: out["timings"][k] for k in _TIMING_KEYS if k in (out.get("timings") or {})}
        rer, tot = t.get("rerank_ms"), t.get("total_ms")
        durations = {"api": None, "pipeline": pipeline_ms, "retrieval": round(tot - rer, 1) if tot is not None and rer is not None else tot, "reranking": rer,
                     "generation": round(out["latency_s"] * 1000) if mode == "llm" and out.get("latency_s") is not None else None}
        if status == "llm_unavailable":
            available = False
            failure = next((n for n in notes if n in _FAILURE_NOTES), None)      # message précis déjà fourni par l'agent (assaini)
            message = C.LLM_UNAVAILABLE_PUBLIC if not llm_up else (failure or GENERATION_FAILED_MESSAGE)
        else:
            available, message = llm_up, (None if llm_up else C.LLM_UNAVAILABLE_PUBLIC)
        payload = {"question": q, "status": status, "found": found, "clarify": clarify, "mode": mode, "reason": out.get("reason"), "answer": out.get("answer"),
                   "citations": cited if mode == "llm" else sources, "sources": sources, "notes": notes, "disclaimer": out.get("disclaimer"),
                   "model": out.get("model"), "provider": out.get("provider"), "retriever": out.get("retriever"), "latency_s": out.get("latency_s"),
                   "timings": t, "durations_ms": durations,
                   "llm": {"requested": True, "available": available, "message": message}}
        if status == "llm_unavailable" and message not in payload["notes"]:
            payload["notes"].insert(0, message)
        # Pas de réponse directe MAIS des textes retrouvés (génération impossible, ou le modèle a refusé de répondre à partir d'eux) : on les présente et on les décrit.
        # Aucun texte retrouvé (refus de la recherche, question ambiguë) : rien à présenter, les messages habituels s'appliquent.
        texts = related_texts(sources) if (status == "llm_unavailable" or (status == "refused" and sources)) else []
        payload["texts"] = texts
        payload["texts_intro"] = C.NO_DIRECT_ANSWER_MESSAGE if texts else None
        if self.debug:
            payload["debug"] = {"rerank_best": (out.get("timings") or {}).get("rerank_best"), "llm_timings": out.get("llm_timings")}
        return payload
