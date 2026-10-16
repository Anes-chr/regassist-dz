# RegAssist DZ — Production & Linux Deployment Guide

This directory contains the production-hardened deployment configuration for RegAssist DZ on Linux (Ubuntu 24.04 LTS / 4 vCPU / 8 GB RAM VPS) and containerized environments.

---

## Architecture Overview

```
[ Internet Client (Browser) ]
              │  (HTTPS : 443)
              ▼
    [ Nginx Reverse Proxy ]
         │ (Drop unknown SNI/Host - HTTP 444)
         │ (Overwrites X-Forwarded-* headers)
         ▼ (HTTP : 8790)
   [ Gunicorn WSGI Worker ] (deploy.wsgi:app)
         │ (1 worker, 4 gthread threads)
         │ (Shared single-flight inference lock)
         │ (HTTP 429 + Retry-After: 30 on contention)
         ▼
   [ RegAssist Core Engine ]
         ├─ BM25 Lexical + multilingual-e5-small Embeddings
         ├─ ONNX mmarco Reranker
         └─ Local CPU llama-server (127.0.0.1:8187, Qwen3-4B Q4_K_M)
```

---

## Directory Contents

- `requirements-deploy.txt`: Production requirements extending root `requirements.txt` with `gunicorn==23.0.0`.
- `linux_env.sh`: Non-intrusive Linux path mapping and environment setup.
- `start_llm_linux.sh`: Script to launch `llama-server` (b11411 build) with matching arguments on Linux.
- `wsgi.py`: Gunicorn WSGI entry point ensuring single `Service` instance and thread safety.
- `nginx-regassist.conf`: Hardened reverse proxy configuration with catch-all TLS dropping.
- `systemd/`: Service supervision unit files (`regassist-llm.service`, `regassist-web.service`).
- `regassist.env`: Environment file containing production secrets and path configurations.
- `test_proxy_security.sh`: 3-case automated test script for host/origin security and header spoofing defenses.
- `test_concurrency_and_load.sh`: End-to-end contention test validating sibling thread liveness and HTTP 429 `Retry-After`.
- `run_linux_poc.sh`: Automation script for running the 3 diagnostic queries and measuring RSS RAM on Linux.

---

## Deployment Steps (Ubuntu 24.04 LTS)

### 1. System Preparation
```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip nginx curl
sudo useradd -r -s /bin/false regassist
```

### 2. Directory Layout
```bash
sudo mkdir -p /opt/regassist-dz /opt/regassist-data/llm /var/log/regassist
sudo chown -R regassist:regassist /opt/regassist-dz /opt/regassist-data /var/log/regassist
```

### 3. Virtual Environment & Dependencies
```bash
cd /opt/regassist-dz
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r deploy/requirements-deploy.txt
```

### 4. Service Installation
```bash
sudo cp deploy/systemd/regassist-llm.service /etc/systemd/system/
sudo cp deploy/systemd/regassist-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now regassist-llm.service
sudo systemctl enable --now regassist-web.service
```

### 5. Nginx Configuration
```bash
sudo cp deploy/nginx-regassist.conf /etc/nginx/sites-available/regassist
sudo ln -s /etc/nginx/sites-available/regassist /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```
