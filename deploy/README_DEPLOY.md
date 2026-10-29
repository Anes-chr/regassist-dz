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

## Access Control

Gunicorn has **no access gate** in this deployment: the access code of the Windows LAN mode lives in `local_app/lan.py` and is not wired into `deploy/wsgi.py`. The nginx configuration therefore requires **HTTP Basic authentication on the whole site** (step 6). Share the password only with the intended evaluators: the service exposes an unvalidated legal assistant (status NO-GO PROVISOIRE) and must not be open to the general public.

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

## Quick path: `setup_vps.sh`

On a fresh Ubuntu 24.04 server whose DNS name already points to it, as root:
```bash
apt-get update && apt-get install -y git certbot
certbot register --agree-tos --register-unsafely-without-email --no-eff-email   # or give an e-mail address instead
git clone https://github.com/SalimMabed/regassist-dz.git /opt/regassist-dz
bash /opt/regassist-dz/deploy/setup_vps.sh regassist.example.org
```
The script runs steps 1 to 7 below (it refuses to start when memory, disk or DNS are insufficient), prints a result block without secrets and writes the Basic-auth login to `/root/regassist-access.txt` (mode 600). It can be re-run after a failure. Without the `certbot register` line above, certbot asks for an e-mail address and the Let's Encrypt terms interactively.

**First real run (2026-10-29).** Octenium VPS Ultimate: 4 vCPU, 8 GB RAM, 500 GB HDD (RAID 10), Intel Xeon E5-2690 v2 (Ivy Bridge: **AVX but no AVX2**), Ubuntu 24.04. Models and corpus were downloaded and verified in about one minute, the whole setup took about 15 minutes. Checks: HTTP 301, HTTPS 401 without password and 200 with it, valid Let's Encrypt certificate. One real question ("Quel est le plafond d'indemnisation par déposant ?") returned `answered` with 3 sources and 1 citation in **148 s** (generation 144.7 s). On a CPU without AVX2 the reranker and llama.cpp run, but slower, and ranks may differ slightly from an AVX2 machine (see `docs/OUTDATED_AMOUNTS_STUDY.md`).

Two defects found by that run are fixed: the shell scripts were committed without the executable bit (systemd could not start `start_llm_linux.sh`), and the virtualenv was created after the data step that needs numpy.

## Deployment Steps (Ubuntu 24.04 LTS)

### 1. System Preparation
```bash
sudo apt update && sudo apt install -y python3 python3-venv python3-pip nginx curl libgomp1 git certbot apache2-utils ufw
sudo useradd -r -s /bin/false regassist
# The reranker (model_quint8_avx2.onnx) needs AVX2: this must print "avx2". If it prints nothing, stop here.
lscpu | grep -o -m1 avx2
```

### 2. Directory Layout
```bash
sudo git clone https://github.com/SalimMabed/regassist-dz.git /opt/regassist-dz
sudo mkdir -p /opt/regassist-data/llm /var/log/regassist
sudo chown -R regassist:regassist /opt/regassist-dz /opt/regassist-data /var/log/regassist
```
The repository (about 1.1 GB with the corpus) keeps its bytes as committed (`.gitattributes` sets `* -text`): do not convert line endings, the frozen-system hashes depend on them.

### 3. Populate Data Folders (`/opt/regassist-data/llm`)

On a fresh VPS, model files, vectors, and corpus snapshots must be initialized in `/opt/regassist-data/llm`. You can run the automated helper script or execute the commands manually.

#### Option A: Automated (Recommended)
```bash
sudo bash deploy/populate_data_linux.sh /opt/regassist-data/llm
```

#### Option B: Manual Step-by-Step

1. **Create subdirectories:**
```bash
mkdir -p /opt/regassist-data/llm/{models/embeddings/multilingual-e5-small/onnx,models/rerankers/mmarco-mMiniLMv2-L12-H384/onnx,llama.cpp/b11411,index,snapshots/corpus_phase4}
```

2. **Download Qwen3-4B-Instruct GGUF (2.5 GB) & verify SHA-256:**
```bash
curl -L -C - --retry 10 -o /opt/regassist-data/llm/models/qwen3-4b-instruct-2507-q4_k_m.gguf \
  https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/main/Qwen3-4B-Instruct-2507-Q4_K_M.gguf

echo "3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597  /opt/regassist-data/llm/models/qwen3-4b-instruct-2507-q4_k_m.gguf" | sha256sum -c
```

3. **Download Embedding & Reranker models & verify SHA-256:**
```bash
# multilingual-e5-small (Embedding)
curl -L -C - --retry 10 -o /opt/regassist-data/llm/models/embeddings/multilingual-e5-small/onnx/model.onnx \
  https://huggingface.co/intfloat/multilingual-e5-small/resolve/main/onnx/model.onnx
curl -L -C - --retry 10 -o /opt/regassist-data/llm/models/embeddings/multilingual-e5-small/tokenizer.json \
  https://huggingface.co/intfloat/multilingual-e5-small/resolve/main/tokenizer.json

echo "ca456c06b3a9505ddfd9131408916dd79290368331e7d76bb621f1cba6bc8665  /opt/regassist-data/llm/models/embeddings/multilingual-e5-small/onnx/model.onnx" | sha256sum -c
echo "0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39  /opt/regassist-data/llm/models/embeddings/multilingual-e5-small/tokenizer.json" | sha256sum -c

# mmarco-mMiniLMv2-L12-H384 (Reranker)
curl -L -C - --retry 10 -o /opt/regassist-data/llm/models/rerankers/mmarco-mMiniLMv2-L12-H384/onnx/model_quint8_avx2.onnx \
  https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1/resolve/main/onnx/model_quint8_avx2.onnx
curl -L -C - --retry 10 -o /opt/regassist-data/llm/models/rerankers/mmarco-mMiniLMv2-L12-H384/tokenizer.json \
  https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1/resolve/main/tokenizer.json

echo "6c2513767fb63d008a4377bef7a7a3555433d9436342bb53e35a3a72ffc52d4b  /opt/regassist-data/llm/models/rerankers/mmarco-mMiniLMv2-L12-H384/onnx/model_quint8_avx2.onnx" | sha256sum -c
echo "62c24cdc13d4c9952d63718d6c9fa4c287974249e16b7ade6d5a85e7bbb75626  /opt/regassist-data/llm/models/rerankers/mmarco-mMiniLMv2-L12-H384/tokenizer.json" | sha256sum -c
```

4. **Install llama.cpp b11411 (Ubuntu Linux x64) & verify SHA-256:**
```bash
# Download official release tar.gz archive
curl -L -C - --retry 10 -o /tmp/llama-b11411-bin-ubuntu-x64.tar.gz \
  https://github.com/ggml-org/llama.cpp/releases/download/b11411/llama-b11411-bin-ubuntu-x64.tar.gz

# Cryptographic SHA-256 integrity verification
echo "4f0ff85bc63a1df9a3465fa99c78339ac5a2ac0e8dfa864a12d28f3521ff6111  /tmp/llama-b11411-bin-ubuntu-x64.tar.gz" | sha256sum -c

# Extract entire archive including all required shared libraries (.so)
tar -xzf /tmp/llama-b11411-bin-ubuntu-x64.tar.gz --strip-components=1 -C /opt/regassist-data/llm/llama.cpp/b11411/
chmod +x /opt/regassist-data/llm/llama.cpp/b11411/llama-server
echo "b11411" > /opt/regassist-data/llm/llama.cpp/CURRENT_TAG.txt
rm -f /tmp/llama-b11411-bin-ubuntu-x64.tar.gz
```

5. **Copy Corpus Snapshot, Seed Vectors & Set Permissions:**
```bash
# Copy snapshot files
cp -n /opt/regassist-dz/replication/snapshots/corpus_phase4/* /opt/regassist-data/llm/snapshots/corpus_phase4/

# Seed and link runtime vector keys
cd /opt/regassist-dz
python3 -m deploy.ensure_vectors /opt/regassist-data/llm/index

# Set ownership of data root to regassist service user
sudo chown -R regassist:regassist /opt/regassist-data
```

### 4. Virtual Environment & Dependencies
```bash
cd /opt/regassist-dz
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r deploy/requirements-deploy.txt
```

### 5. Service Installation
```bash
sudo cp deploy/systemd/regassist-llm.service /etc/systemd/system/
sudo cp deploy/systemd/regassist-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now regassist-llm.service
sudo systemctl enable --now regassist-web.service
```

### 6. Domain, TLS Certificate, Private Access and Nginx
The domain must already resolve to this server (DNS `A` record) before the certificate is requested.
```bash
cd /opt/regassist-dz
DOMAIN=regassist.example.org     # replace with your own name

# Domain in the nginx site and in the allowed Host / Origin lists of the application
sed -i "s/YOUR_DOMAIN.COM/${DOMAIN}/g" deploy/nginx-regassist.conf
sed -i "s/regassist.example.com/${DOMAIN}/g" deploy/regassist.env
sudo systemctl restart regassist-web.service

# Let's Encrypt certificate (valid 90 days; renewal is not configured here). The stock nginx site also
# claims port 80 as default_server and would make "nginx -t" fail: remove it.
sudo rm -f /etc/nginx/sites-enabled/default
sudo systemctl stop nginx
sudo certbot certonly --standalone -d "${DOMAIN}"

# Private access: one user, a long random password (write it down, it is shown only here)
openssl rand -base64 18
sudo htpasswd -c /etc/nginx/regassist.htpasswd judge      # prompts twice for that password
sudo chown root:www-data /etc/nginx/regassist.htpasswd && sudo chmod 640 /etc/nginx/regassist.htpasswd

# Site activation
sudo cp deploy/nginx-regassist.conf /etc/nginx/sites-available/regassist
sudo ln -sf /etc/nginx/sites-available/regassist /etc/nginx/sites-enabled/regassist
sudo nginx -t && sudo systemctl start nginx

# Firewall: SSH, HTTP (redirect to HTTPS) and HTTPS only
sudo ufw allow OpenSSH && sudo ufw allow 80,443/tcp && sudo ufw --force enable
```

### 7. Verification & Security Tests
```bash
# Verify health endpoint
curl -s http://127.0.0.1:8790/api/health
# Verify readiness & provider status
curl -s http://127.0.0.1:8790/api/status

# Through nginx: 401 without the password, then {"status":"ok"} with it (prompts for the password)
curl -s -o /dev/null -w "%{http_code}\n" "https://${DOMAIN}/api/health"
curl -s -u judge "https://${DOMAIN}/api/health"

# Run automated proxy security & spoofing defenses test
bash deploy/test_proxy_security.sh

# Run concurrency and contention test
bash deploy/test_concurrency_and_load.sh
```
Both test scripts target `http://127.0.0.1:8790` (Gunicorn directly, without nginx) unless a URL is given; run them without argument. Through nginx they would need the Basic-auth password.
