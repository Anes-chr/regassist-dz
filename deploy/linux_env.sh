#!/usr/bin/env bash
# ==============================================================================
# RegAssist DZ - Linux Environment & Path Configuration Adapter
# ==============================================================================
# Sets up path resolutions and environment variables for Ubuntu Linux 24.04 LTS
# without modifying any tracked file in the frozen engine (agent_fr/).

set -e

export REGASSIST_ROOT="${REGASSIST_ROOT:-/opt/regassist-dz}"
export REGASSIST_DATA_ROOT="${REGASSIST_DATA_ROOT:-/opt/regassist-data}"
export LLM_ROOT="${REGASSIST_DATA_ROOT}/llm"

# Ensure runtime directories exist
mkdir -p "${REGASSIST_ROOT}/local_app/runtime"
mkdir -p "/var/log/regassist" 2>/dev/null || mkdir -p "${REGASSIST_ROOT}/runtime/logs"

# Export required environment variables
export LOCAL_APP_RUNTIME="${LOCAL_APP_RUNTIME:-${REGASSIST_ROOT}/local_app/runtime}"
export LOCAL_APP_PORT="${LOCAL_APP_PORT:-8790}"
export PYTHONIOENCODING="utf-8"

# Path configuration for models, index, and corpus
export AGENT_EMBED_DIR="${LLM_ROOT}/models/embeddings/multilingual-e5-small"
export AGENT_RERANK_DIR="${LLM_ROOT}/models/rerankers/mmarco-mMiniLMv2-L12-H384"
export AGENT_VECTOR_DIR="${LLM_ROOT}/index"
export AGENT_CORPUS_DIR="${LLM_ROOT}/snapshots/corpus_phase4"

# Local LLM endpoint and shared libraries
export AGENT_LOCAL_URL="http://127.0.0.1:8187"
export LD_LIBRARY_PATH="${LLM_ROOT}/llama.cpp/b11411:${LD_LIBRARY_PATH:-}"

# Idempotently ensure vector index compatibility for this Linux deployment path
if command -v python3 >/dev/null 2>&1; then
    PYTHONPATH="${REGASSIST_ROOT}:${PYTHONPATH:-}" python3 -m deploy.ensure_vectors "${AGENT_VECTOR_DIR}" 2>/dev/null || true
fi

echo "[linux_env.sh] Linux environment configured. LLM_ROOT=${LLM_ROOT}"

