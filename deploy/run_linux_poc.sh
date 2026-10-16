#!/usr/bin/env bash
# ==============================================================================
# RegAssist DZ - Automated Linux Compatibility Proof of Concept (POC)
# ==============================================================================
# Runs the full pipeline on Linux:
# Official corpus -> Hybrid retrieval -> ONNX reranker -> Local Qwen3-4B -> Cited JSON
#
# Measures:
# - Client round-trip latency & internal server durations
# - Peak RSS RAM usage (VmHWM) of Python & llama-server
# - Saves output JSONs to $OUTPUT_DIR (default: ./diagnostics_linux)
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
OUTPUT_DIR="${OUTPUT_DIR:-${HOME}/RegAssistDiagnosticsLinux}"

mkdir -p "${OUTPUT_DIR}"
echo "=================================================="
echo "RegAssist DZ - Linux Proof of Concept (POC)"
echo "Output Directory: ${OUTPUT_DIR}"
echo "Project Root    : ${PROJECT_ROOT}"
echo "=================================================="

# Check if llama-server and local_app are running
APP_PORT="${LOCAL_APP_PORT:-8790}"
BASE_URL="http://127.0.0.1:${APP_PORT}"

echo "Checking runtime status on ${BASE_URL}/api/status..."
if ! curl -s "${BASE_URL}/api/status" > "${OUTPUT_DIR}/linux_status.json"; then
    echo "ERROR: Server at ${BASE_URL} is unreachable."
    echo "Ensure llama-server and local_app (or Gunicorn) are running."
    exit 1
fi

echo "Status captured successfully. Checking readiness..."
APP_STATE=$(python3 -c "import json; s=json.load(open('${OUTPUT_DIR}/linux_status.json')); print(s.get('app',{}).get('state','unknown'))")
echo "App state: ${APP_STATE}"

# Diagnostic queries
declare -A QUERIES=(
    ["linux_diag_q1"]="Quelles sont les conditions de constitution du capital minimum des banques ?"
    ["linux_diag_q2"]="Quel est le plafond d'indemnisation par déposant ?"
    ["linux_diag_q3"]="Quelle est la capitale de la France ?"
)

for Q_ID in "linux_diag_q1" "linux_diag_q2" "linux_diag_q3"; do
    QUESTION="${QUERIES[$Q_ID]}"
    echo ""
    echo "--- Executing Query: ${Q_ID} ---"
    echo "Question: ${QUESTION}"

    T_START=$(date +%s%N)
    curl -s -X POST "${BASE_URL}/api/chat" \
        -H "Content-Type: application/json" \
        -d "{\"question\": \"${QUESTION}\"}" \
        > "${OUTPUT_DIR}/${Q_ID}.json"
    T_END=$(date +%s%N)

    DUR_MS=$(( (T_END - T_START) / 1000000 ))
    echo "Client Round-Trip: ${DUR_MS} ms"

    # Extract timings and status
    python3 -c "
import json
try:
    with open('${OUTPUT_DIR}/${Q_ID}.json') as f:
        data = json.load(f)
    print('Status   :', data.get('status'))
    durs = data.get('durations_ms', {})
    for k, v in durs.items():
        print(f'Duration {k}: {v} ms')
    sources = data.get('sources', [])
    print(f'Sources count: {len(sources)}')
except Exception as e:
    print('Error parsing output:', e)
"
done

# Measure Peak RSS RAM usage
echo ""
echo "--- Peak Memory Usage (RSS) ---"
ps -o pid,rss,vsz,comm -C python3,python,llama-server,gunicorn 2>/dev/null || ps aux | grep -E 'python|llama|gunicorn' | grep -v grep || true

echo ""
echo "Linux POC queries executed and archived in ${OUTPUT_DIR}."
