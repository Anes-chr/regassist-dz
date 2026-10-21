#!/usr/bin/env bash
# ==============================================================================
# deploy/populate_data_linux.sh
# ==============================================================================
# Automated, idempotent script to populate /opt/regassist-data/llm on a fresh
# Linux VPS (Ubuntu 24.04 LTS) for RegAssist DZ.
#
# Downloads models, verifies cryptographic SHA-256 hashes against
# PHASE_4_FROZEN.manifest.json, sets up the frozen corpus snapshot, and runs
# deploy.ensure_vectors to seed the runtime vector index.
#
# Usage:
#   sudo bash deploy/populate_data_linux.sh [/opt/regassist-data/llm]
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LLM_ROOT="${1:-${LLM_ROOT:-/opt/regassist-data/llm}}"

echo "========================================================================"
echo "RegAssist DZ — Initialisation des données Linux VPS"
echo "Racine des données : ${LLM_ROOT}"
echo "Dépôt Git          : ${REPO_ROOT}"
echo "========================================================================"

# 1. Vérification des outils requis
for cmd in curl unzip python3 sha256sum; do
    if ! command -v "${cmd}" >/dev/null 2>&1; then
        echo "ERREUR: Commande requise introuvable : ${cmd}. Installez-la avec apt." >&2
        exit 1
    fi
done

# 2. Arborescence
echo "[1/5] Création de l'arborescence..."
mkdir -p "${LLM_ROOT}/models/embeddings/multilingual-e5-small/onnx"
mkdir -p "${LLM_ROOT}/models/rerankers/mmarco-mMiniLMv2-L12-H384/onnx"
mkdir -p "${LLM_ROOT}/llama.cpp/b11411"
mkdir -p "${LLM_ROOT}/index"
mkdir -p "${LLM_ROOT}/snapshots/corpus_phase4"

# Fonction utilitaire de téléchargement et vérification SHA-256
download_and_verify() {
    local url="$1"
    local dest="$2"
    local expected_sha="$3"
    local label="$4"

    if [[ -f "${dest}" ]]; then
        local current_sha
        current_sha="$(sha256sum "${dest}" | awk '{print $1}')"
        if [[ "${current_sha}" == "${expected_sha}" ]]; then
            echo "  [OK] ${label} (déjà présent et conforme)"
            return 0
        else
            echo "  [AVERTISSEMENT] Empreinte non conforme pour ${dest}, re-téléchargement..."
            rm -f "${dest}"
        fi
    fi

    echo "  [TÉLÉCHARGEMENT] ${label}..."
    local part="${dest}.part"
    curl -L -C - --retry 10 --retry-delay 3 --connect-timeout 20 -sS -o "${part}" "${url}"
    
    local downloaded_sha
    downloaded_sha="$(sha256sum "${part}" | awk '{print $1}')"
    if [[ "${downloaded_sha}" != "${expected_sha}" ]]; then
        echo "  [ERREUR] Échec de validation SHA-256 pour ${label} :" >&2
        echo "           Attendu : ${expected_sha}" >&2
        echo "           Obtenu  : ${downloaded_sha}" >&2
        rm -f "${part}"
        return 1
    fi

    mv "${part}" "${dest}"
    echo "  [SUCCÈS] ${label} validé par SHA-256."
}

# 3. Modèles (GGUF, Embedding ONNX, Reranker ONNX)
echo "[2/5] Téléchargement et validation des modèles IA..."

# 3a. Qwen3-4B-Instruct GGUF
download_and_verify \
    "https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/main/Qwen3-4B-Instruct-2507-Q4_K_M.gguf" \
    "${LLM_ROOT}/models/qwen3-4b-instruct-2507-q4_k_m.gguf" \
    "3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597" \
    "Qwen3-4B-Instruct-2507-Q4_K_M.gguf (2.5 Go)"

# 3b. multilingual-e5-small (ONNX + Tokenizer)
download_and_verify \
    "https://huggingface.co/intfloat/multilingual-e5-small/resolve/main/onnx/model.onnx" \
    "${LLM_ROOT}/models/embeddings/multilingual-e5-small/onnx/model.onnx" \
    "ca456c06b3a9505ddfd9131408916dd79290368331e7d76bb621f1cba6bc8665" \
    "multilingual-e5-small model.onnx"

download_and_verify \
    "https://huggingface.co/intfloat/multilingual-e5-small/resolve/main/tokenizer.json" \
    "${LLM_ROOT}/models/embeddings/multilingual-e5-small/tokenizer.json" \
    "0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39" \
    "multilingual-e5-small tokenizer.json"

# 3c. mmarco-mMiniLMv2-L12-H384 (ONNX quint8 + Tokenizer)
download_and_verify \
    "https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1/resolve/main/onnx/model_quint8_avx2.onnx" \
    "${LLM_ROOT}/models/rerankers/mmarco-mMiniLMv2-L12-H384/onnx/model_quint8_avx2.onnx" \
    "6c2513767fb63d008a4377bef7a7a3555433d9436342bb53e35a3a72ffc52d4b" \
    "mmarco-mMiniLMv2 model_quint8_avx2.onnx"

download_and_verify \
    "https://huggingface.co/cross-encoder/mmarco-mMiniLMv2-L12-H384-v1/resolve/main/tokenizer.json" \
    "${LLM_ROOT}/models/rerankers/mmarco-mMiniLMv2-L12-H384/tokenizer.json" \
    "62c24cdc13d4c9952d63718d6c9fa4c287974249e16b7ade6d5a85e7bbb75626" \
    "mmarco-mMiniLMv2 tokenizer.json"

# 4. llama.cpp b11411 binaire Linux Ubuntu
echo "[3/5] Installation du binaire llama-server b11411..."
LLAMA_BIN="${LLM_ROOT}/llama.cpp/b11411/llama-server"
if [[ ! -x "${LLAMA_BIN}" ]]; then
    ZIP_TMP="/tmp/llama-b11411-bin-ubuntu-x64.zip"
    echo "  Téléchargement de llama.cpp b11411 Ubuntu x64..."
    curl -L -C - --retry 10 -sS -o "${ZIP_TMP}" \
        "https://github.com/ggml-org/llama.cpp/releases/download/b11411/llama-b11411-bin-ubuntu-x64.zip"
    
    unzip -q -j -o "${ZIP_TMP}" "build/bin/llama-server" -d "${LLM_ROOT}/llama.cpp/b11411/" || \
    unzip -q -j -o "${ZIP_TMP}" "*llama-server*" -d "${LLM_ROOT}/llama.cpp/b11411/"
    
    chmod +x "${LLAMA_BIN}"
    echo "b11411" > "${LLM_ROOT}/llama.cpp/CURRENT_TAG.txt"
    rm -f "${ZIP_TMP}"
    echo "  [SUCCÈS] llama-server b11411 installé sous ${LLAMA_BIN}"
else
    echo "  [OK] llama-server b11411 déjà exécutable."
fi

# 5. Instantané du corpus officiel
echo "[4/5] Copie de l'instantané du corpus Phase 4..."
SRC_SNAP="${REPO_ROOT}/replication/snapshots/corpus_phase4"
DST_SNAP="${LLM_ROOT}/snapshots/corpus_phase4"
if [[ -d "${SRC_SNAP}" ]]; then
    for f in "${SRC_SNAP}"/*; do
        if [[ -f "${f}" ]]; then
            cp -n "${f}" "${DST_SNAP}/"
        fi
    done
    echo "  [OK] Fichiers du corpus copiés vers ${DST_SNAP}"
else
    echo "  [AVERTISSEMENT] Dossier ${SRC_SNAP} introuvable dans le dépôt."
fi

# 6. Peuplement des vecteurs via deploy.ensure_vectors
echo "[5/5] Initialisation cryptographique des vecteurs..."
export PYTHONPATH="${REPO_ROOT}:${PYTHONPATH:-}"
python3 -m deploy.ensure_vectors "${LLM_ROOT}/index"

echo "========================================================================"
echo "SUCCÈS : Données initialisées avec succès sous ${LLM_ROOT}."
echo "Vous pouvez démarrer les services systemd :"
echo "  sudo systemctl start regassist-llm.service"
echo "  sudo systemctl start regassist-web.service"
echo "========================================================================"
