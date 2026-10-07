"""Démarrage : python -m local_app   (ou .\\start_local.ps1 à la racine du projet, qui démarre aussi llama-server si nécessaire)."""
import sys
import threading

from . import config as C
from .server import LocalServer, create_app, port_in_use
from .service import Service, check_environment, setup_logging


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    port = C.port()
    report = check_environment()                         # refuse de démarrer si l'environnement s'écarte du système gelé ; neutralise tout LLM distant
    if port_in_use(port):
        print(f"Le port {port} est déjà utilisé (utiliser LOCAL_APP_PORT ou .\\start_local.ps1 -Port N).", file=sys.stderr)
        return 2
    setup_logging()
    svc = Service(env_report=report)
    try:
        srv = LocalServer(C.HOST, port, create_app(svc, port))
    except OSError as e:
        print(f"Impossible de lier {C.HOST}:{port} ({type(e).__name__}).", file=sys.stderr)
        return 2
    if report["neutralised"]:
        svc.log("env_neutralised", names=report["neutralised"])
    if report["engine_overrides"]:
        svc.log("env_engine_overrides", names=report["engine_overrides"])
    svc.log("start", host=C.HOST, port=port, debug=svc.debug, log_questions=C.log_questions())
    print(f"Application locale : http://{C.HOST}:{port}  (chargement du moteur de recherche en cours ; /api/status indique quand il est prêt)", flush=True)
    threading.Thread(target=svc.warm_up, name="warm-up", daemon=True).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        svc.log("stop")
        srv.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
