"""Application Flask locale : API JSON + interface statique servies par le MÊME serveur, donc une seule origine (http://127.0.0.1:PORT).

Conséquences de sécurité :
* aucune requête inter-origines n'est nécessaire, donc AUCUN en-tête CORS n'est jamais émis (le navigateur refuse toute lecture depuis un autre site) ;
* l'en-tête Host doit être 127.0.0.1:PORT ou localhost:PORT (protège contre le « DNS rebinding ») et Origin, s'il est présent, doit être cette même origine ;
  en mode réseau OPTIONNEL (lan.py, désactivé par défaut) s'y ajoutent les noms de cette machine, et un code d'accès est exigé ;
* la politique CSP n'autorise que les fichiers de l'application : pas de CDN, pas de script distant, pas de connexion vers un autre hôte.
"""
import os
import socket

from flask import Flask, jsonify, make_response, redirect, request, send_from_directory
from werkzeug.exceptions import HTTPException
from werkzeug.serving import ThreadedWSGIServer

from . import config as C
from . import lan as L
from .service import Service, ServiceError, check_environment, setup_logging

CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; font-src 'self'; "
       "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
_PAGES = {"": "index.html", "index.html": "index.html", "app.css": "app.css", "app.js": "app.js", "favicon.svg": "favicon.svg", "login.css": "login.css"}
# Mode réseau seulement : ce qui reste accessible sans code d'accès (la page d'accès et ses ressources, la sonde de vie qui ne renvoie que « ok »).
_PUBLIC_IN_LAN = {"/login", "/login.css", "/favicon.svg", "/favicon.ico", "/api/health"}


def create_app(service: Service, port: int | None = None, lan: "L.LanAccess | None" = None) -> Flask:
    """`lan` = None (défaut) : application locale, 127.0.0.1 seulement. `lan` fourni : accès réseau avec code d'accès (voir lan.py)."""
    port = port or C.port()
    hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    if lan is not None:
        hosts |= lan.hosts(port)
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
            if lan is not None:
                return err(403, "forbidden_host", "Accès refusé : utilisez l'adresse qui vous a été communiquée.")
            return err(403, "forbidden_host", "Accès refusé : cette application n'est accessible que via http://127.0.0.1:%d." % port)
        origin = request.headers.get("Origin")
        if origin is not None and origin not in origins:
            return err(403, "forbidden_origin", "Accès refusé : origine non autorisée.")
        if request.path.startswith("/api/") and request.headers.get("Sec-Fetch-Site", "same-origin") in ("cross-site", "same-site"):
            return err(403, "forbidden_origin", "Accès refusé : origine non autorisée.")
        if lan is not None and request.path not in _PUBLIC_IN_LAN and not lan.valid(request.cookies.get(L.COOKIE)):
            if request.path.startswith("/api/"):
                return err(401, "auth_required", "Session expirée ou absente : rechargez la page et saisissez le code d'accès.")
            return redirect("/login", code=302)
        return None

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if lan is None:
            return err(404, "not_found", "Ressource introuvable.")
        if lan.open:                                         # accès libre choisi explicitement : pas de page de connexion
            return redirect("/", code=302)
        if request.method == "GET":
            r = make_response(L.login_page())
        else:
            addr = request.remote_addr or "?"
            token, wait = lan.attempt(addr, request.form.get("code", ""))
            if token:
                service.log("login_ok", addr=addr)
                r = redirect("/", code=303)
                r.set_cookie(L.COOKIE, token, max_age=L.SESSION_TTL_S, httponly=True, samesite="Strict", path="/")
                return r
            service.log("login_failed", addr=addr, locked_s=wait or None)
            if wait:
                r = make_response(L.login_page("Trop d'essais. Réessayez dans %d minute(s)." % max(1, -(-wait // 60))), 429)
            else:
                r = make_response(L.login_page("Code d'accès incorrect."), 401)
        r.headers["Content-Type"] = "text/html; charset=utf-8"
        return r

    @app.after_request
    def headers(resp):
        resp.headers["Content-Security-Policy"] = L.LOGIN_CSP if request.path == "/login" else CSP
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        resp.headers["Cache-Control"] = "no-store" if request.path.startswith("/api/") or request.path == "/login" else "no-cache"
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


def make_servers(app: Flask, port: int, lan_ip: str | None = None) -> list:
    """Serveur de la boucle locale (toujours) + serveur de l'adresse réseau privée (mode réseau seulement). Jamais 0.0.0.0 : les autres cartes
    (VMware, Hyper-V…) ne sont pas exposées. Si la seconde liaison échoue, la première est refermée et l'erreur remonte."""
    servers = []
    try:
        for host in (C.HOST, lan_ip):
            if host:
                servers.append(LocalServer(host, port, app))
    except (OSError, SystemExit):                      # werkzeug appelle sys.exit(1) quand l'adresse est déjà occupée : on le convertit en OSError
        for s in servers:
            s.server_close()
        raise OSError(f"liaison impossible sur {host}:{port}") from None
    return servers


def port_in_use(port: int, host: str | None = None) -> bool:
    try:
        with socket.create_connection((host or C.HOST, port), timeout=0.5):
            return True
    except OSError:
        return False
