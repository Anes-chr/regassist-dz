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

### 3. Populate Data Folders (`/opt/regassist-data/llm`)

On a fresh VPS, model files, vectors, and corpus snapshots must be initialized in `/opt/regassist-data/llm`. You can run the automated helper script or execute the commands manually.

#### Option A: Automated (Recommended)
```bash
sudo bash deploy/populate_data_linux.sh /opt/regassist-data/llm
sudo chown -R regassist:regassist /opt/regassist-data
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

4. **Install llama.cpp b11411 (Ubuntu Linux x64):**
```bash
curl -L -C - --retry 10 -o /tmp/llama-b11411-bin-ubuntu-x64.zip \
  https://github.com/ggml-org/llama.cpp/releases/download/b11411/llama-b11411-bin-ubuntu-x64.zip
unzip -j -o /tmp/llama-b11411-bin-ubuntu-x64.zip "build/bin/llama-server" -d /opt/regassist-data/llm/llama.cpp/b11411/ || \
unzip -j -o /tmp/llama-b11411-bin-ubuntu-x64.zip "*llama-server*" -d /opt/regassist-data/llm/llama.cpp/b11411/
chmod +x /opt/regassist-data/llm/llama.cpp/b11411/llama-server
echo "b11411" > /opt/regassist-data/llm/llama.cpp/CURRENT_TAG.txt
rm -f /tmp/llama-b11411-bin-ubuntu-x64.zip
```

5. **Copy Corpus Snapshot & Seed Vectors:**
```bash
# Copy snapshot files
cp -n /opt/regassist-dz/replication/snapshots/corpus_phase4/* /opt/regassist-data/llm/snapshots/corpus_phase4/

# Seed and link runtime vector keys
cd /opt/regassist-dz
python3 -m deploy.ensure_vectors /opt/regassist-data/llm/index

# Set ownership
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

### 6. Nginx Configuration
```bash
sudo cp deploy/nginx-regassist.conf /etc/nginx/sites-available/regassist
sudo ln -s /etc/nginx/sites-available/regassist /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 7. Verification & Security Tests
```bash
# Verify health endpoint
curl -s http://127.0.0.1:8790/api/health
# Verify readiness & provider status
curl -s http://127.0.0.1:8790/api/status

# Run automated proxy security & spoofing defenses test
bash deploy/test_proxy_security.sh

# Run concurrency and contention test
bash deploy/test_concurrency_and_load.sh
```
