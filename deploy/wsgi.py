"""WSGI entry point for RegAssist DZ in production deployment (Gunicorn).

Target Gunicorn Launch Command:
    gunicorn \\
        --chdir /opt/regassist-dz \\
        --bind 127.0.0.1:8790 \\
        --workers 1 \\
        --worker-class gthread \\
        --threads 4 \\
        --timeout 240 \\
        deploy.wsgi:app

CRITICAL ARCHITECTURAL CONSTRAINTS:
1. Exactly ONE Service instance per Gunicorn worker process.
2. Never pass --preload to Gunicorn; single worker process owns the warm-up thread.
3. All gthread request threads share the exact same Service instance and threading.Lock.
"""
import os
import sys
import threading

# Add project root to sys.path if not present
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from local_app import config as C
from local_app.server import create_app
from local_app.service import Service, check_environment, setup_logging

# 1. Logging setup
setup_logging()

# 2. Idempotent runtime vector mapping (ensures machine/path-specific key exists before check_environment)
runtime_vec_key = None
try:
    from deploy.ensure_vectors import ensure_runtime_vectors
    runtime_vec_key = ensure_runtime_vectors(verbose=False)
except Exception as e:
    print(f"[FATAL] Échec critique du mappage des vecteurs d'exécution (ensure_vectors) : {e}", file=sys.stderr)
    raise RuntimeError(f"Échec critique du mappage des vecteurs d'exécution (ensure_vectors) : {e}") from e

# 2b. Environment check & validation
report = check_environment()

# 3. Instantiate exactly ONE Service instance
port = int(os.environ.get("LOCAL_APP_PORT", str(C.port())))
service = Service(env_report=report)
if runtime_vec_key:
    service.log("runtime_vectors_ready", key=runtime_vec_key)


if report.get("neutralised"):
    service.log("env_neutralised", names=report["neutralised"])
if report.get("engine_overrides"):
    service.log("env_engine_overrides", names=report["engine_overrides"])

deploy_mode = os.environ.get("REGASSIST_DEPLOY_MODE", "local").strip().lower()
allowed_hosts = os.environ.get("REGASSIST_ALLOWED_HOSTS", "")
allowed_origins = os.environ.get("REGASSIST_ALLOWED_ORIGINS", "")

service.log(
    "wsgi_init",
    deploy_mode=deploy_mode,
    port=port,
    allowed_hosts=allowed_hosts,
    allowed_origins=allowed_origins,
)

# 4. Create Flask WSGI application wired to the Service
app = create_app(
    service,
    port=port,
    lan=None,
    deploy_mode=deploy_mode,
    allowed_hosts=allowed_hosts,
    allowed_origins=allowed_origins,
)

# 5. Start background warm-up thread once in this worker process
threading.Thread(target=service.warm_up, name="wsgi-warm-up", daemon=True).start()
