"""Démarrage : python -m local_app   (ou .\\start_local.ps1 à la racine du projet, qui démarre aussi llama-server si nécessaire).
Mode réseau OPTIONNEL : .\\start_local.ps1 -Lan (voir local_app/lan.py et docs/LOCAL_DEPLOYMENT.md)."""
import sys
import threading

from . import config as C
from . import lan as L
from .server import create_app, make_servers, port_in_use
from .service import Service, check_environment, setup_logging


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    port = C.port()
    report = check_environment()                         # refuse de démarrer si l'environnement s'écarte du système gelé ; neutralise tout LLM distant
    lan = L.from_env()                                   # None = application locale seulement (défaut) ; sinon adresse privée + code d'accès obligatoire
    for host in (C.HOST, lan.ip if lan else None):
        if host and port_in_use(port, host):
            print(f"Le port {port} est déjà utilisé sur {host} (utiliser LOCAL_APP_PORT ou .\\start_local.ps1 -Port N).", file=sys.stderr)
            return 2
    setup_logging()
    svc = Service(env_report=report)
    try:
        servers = make_servers(create_app(svc, port, lan), port, lan.ip if lan else None)
    except OSError as e:
        print(f"Impossible de lier le port {port} ({type(e).__name__}).", file=sys.stderr)
        return 2
    if report["neutralised"]:
        svc.log("env_neutralised", names=report["neutralised"])
    if report["engine_overrides"]:
        svc.log("env_engine_overrides", names=report["engine_overrides"])
    svc.log("start", host=C.HOST, port=port, lan_ip=lan.ip if lan else None, lan_open=lan.open if lan else None, debug=svc.debug, log_questions=C.log_questions())   # jamais le code d'accès
    print(f"Application locale : http://{C.HOST}:{port}  (chargement du moteur de recherche en cours ; /api/status indique quand il est prêt)", flush=True)
    if lan:
        print(f"Accès réseau ACTIVÉ sur http://{lan.ip}:{port} ({'SANS code d’accès : libre pour tout poste du réseau' if lan.open else 'code d’accès obligatoire'}, trafic HTTP non chiffré).", flush=True)
    threading.Thread(target=svc.warm_up, name="warm-up", daemon=True).start()
    for extra in servers[1:]:
        threading.Thread(target=extra.serve_forever, name=f"serve-{extra.server_address[0]}", daemon=True).start()
    try:
        servers[0].serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        svc.log("stop")
        for s in servers[1:]:
            s.shutdown()
        for s in servers:
            s.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
