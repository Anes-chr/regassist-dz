"""Application Flask locale : API JSON + interface statique servies par le MÊME serveur, donc une seule origine (http://127.0.0.1:PORT).

Conséquences de sécurité :
* aucune requête inter-origines n'est nécessaire, donc AUCUN en-tête CORS n'est jamais émis (le navigateur refuse toute lecture depuis un autre site) ;
* l'en-tête Host doit être 127.0.0.1:PORT ou localhost:PORT (protège contre le « DNS rebinding ») et Origin, s'il est présent, doit être cette même origine ;
* la politique CSP n'autorise que les fichiers de l'application : pas de CDN, pas de script distant, pas de connexion vers un autre hôte.
"""
import os
import socket

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException
from werkzeug.serving import ThreadedWSGIServer

from . import config as C
from .service import Service, ServiceError, check_environment, setup_logging

CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; font-src 'self'; "
       "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
_PAGES = {"": "index.html", "index.html": "index.html", "app.css": "app.css", "app.js": "app.js", "favicon.svg": "favicon.svg"}


def create_app(service: Service, port: int | None = None) -> Flask:
    port = port or C.port()
    hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    origins = {f"http://{h}" for h in hosts}
    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = C.MAX_BODY_BYTES
    app.json.ensure_ascii = False
    app.json.sort_keys = False

    def err(http: int, code: str, message: str):
        r = jsonify({"error": {"code": code, "message": message}})
        r.status_code = http
        return r

    @app.before_request
    def guard():
        if request.host.lower() not in hosts:
            return err(403, "forbidden_host", "Accès refusé : cette application n'est accessible que via http://127.0.0.1:%d." % port)
        origin = request.headers.get("Origin")
        if origin is not None and origin not in origins:
            return err(403, "forbidden_origin", "Accès refusé : origine non autorisée.")
        if request.path.startswith("/api/") and request.headers.get("Sec-Fetch-Site", "same-origin") in ("cross-site", "same-site"):
            return err(403, "forbidden_origin", "Accès refusé : origine non autorisée.")
        return None

    @app.after_request
    def headers(resp):
        resp.headers["Content-Security-Policy"] = CSP
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        resp.headers["Cache-Control"] = "no-store" if request.path.startswith("/api/") else "no-cache"
        return resp

    @app.errorhandler(ServiceError)
    def service_error(e):
        return err(e.http, e.code, e.message)

    @app.errorhandler(HTTPException)
    def http_error(e):
        messages = {404: "Ressource introuvable.", 405: "Méthode non autorisée.", 413: "Requête trop volumineuse.", 415: "Type de contenu non pris en charge : JSON attendu."}
        return err(e.code or 500, {404: "not_found", 405: "method_not_allowed", 413: "payload_too_large", 415: "unsupported_media_type"}.get(e.code, "http_error"),
                   messages.get(e.code, "Requête non valide."))

    @app.errorhandler(Exception)
    def unexpected(e):
        service.log("unhandled_error", error_type=type(e).__name__)
        return err(500, "internal_error", "Une erreur est survenue. Réessayez dans un instant.")

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/api/status")
    def status():
        return jsonify(service.status())

    @app.post("/api/chat")
    def chat():
        if request.mimetype != "application/json":
            return err(415, "unsupported_media_type", "Type de contenu non pris en charge : JSON attendu.")
        data = request.get_json(silent=True)
        if data is None:
            return err(400, "invalid_json", "Le corps de la requête n'est pas un JSON valide.")
        return jsonify(service.chat(data))

    @app.get("/favicon.ico")
    def favicon_ico():
        return "", 204

    @app.get("/", defaults={"name": ""})
    @app.get("/<path:name>")
    def static_files(name):
        if name not in _PAGES:
            return err(404, "not_found", "Ressource introuvable.")
        return send_from_directory(C.STATIC_DIR, _PAGES[name], max_age=0)

    return app


class LocalServer(ThreadedWSGIServer):
    """Serveur WSGI multi-fil lié à 127.0.0.1, sans partage de port (sous Windows, SO_REUSEADDR laisserait un autre programme se lier au même port)."""
    allow_reuse_address = False

    def server_bind(self):
        if os.name == "nt":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def port_in_use(port: int) -> bool:
    try:
        with socket.create_connection((C.HOST, port), timeout=0.5):
            return True
    except OSError:
        return False
