#!/usr/bin/env bash
# ==============================================================================
# RegAssist DZ - Linux Local LLM Server Launcher (llama.cpp b11411 CPU)
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/linux_env.sh"

LLM_BIN="${LLM_ROOT}/llama.cpp/b11411/llama-server"
LLM_MODEL="${LLM_ROOT}/models/qwen3-4b-instruct-2507-q4_k_m.gguf"
THREADS="${LLM_THREADS:-4}"
CTX="${LLM_CTX:-4096}"
PORT="${LLM_PORT:-8187}"

if [[ ! -x "${LLM_BIN}" ]]; then
    # Fallback to PATH llama-server if b11411 directory binary not found
    if command -v llama-server >/dev/null 2>&1; then
        LLM_BIN="$(command -v llama-server)"
    else
        echo "ERROR: llama-server executable not found at ${LLM_BIN}" >&2
        exit 1
    fi
fi

if [[ ! -f "${LLM_MODEL}" ]]; then
    echo "ERROR: Model weights not found at ${LLM_MODEL}" >&2
    exit 1
fi

echo "Starting llama-server on 127.0.0.1:${PORT} (threads=${THREADS}, ctx=${CTX})..."

exec "${LLM_BIN}" \
    -m "${LLM_MODEL}" \
    -t "${THREADS}" \
    -tb "${THREADS}" \
    -c "${CTX}" \
    --host "127.0.0.1" \
    --port "${PORT}" \
    -np 1 \
    --no-webui \
    -ngl 0 \
    -b 512 \
    -ub 128 \
    -lm none \
    -cram 256 \
    -ctxcp 2 \
    -ctk q8_0 \
    -ctv q8_0 \
    -fa on
