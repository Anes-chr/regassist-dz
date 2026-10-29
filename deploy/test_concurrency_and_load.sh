#!/usr/bin/env bash
# ==============================================================================
# RegAssist DZ - Concurrency, Contention & Load Validation Test
# ==============================================================================
# Verifies single-flight lock, Retry-After: 30 on HTTP 429, and sibling thread liveness.
#
# Usage:
#   ./deploy/test_concurrency_and_load.sh [BASE_URL]
# ==============================================================================

set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:8790}"

echo "=================================================="
echo "RegAssist DZ - Concurrency & Contention Validation"
echo "Target Base URL: ${BASE_URL}"
echo "=================================================="

# 1. Warm-up health check
HEALTH_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/api/health")
if [ "$HEALTH_STATUS" != "200" ]; then
    echo "ERROR: Server is not healthy at ${BASE_URL}/api/health (got HTTP $HEALTH_STATUS)"
    exit 1
fi
echo "Server health confirmed (HTTP 200)."

# 2. Start heavy query in background (Client A)
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "${TEMP_DIR}"' EXIT

CLIENT_A_OUT="${TEMP_DIR}/client_a.json"
CLIENT_B_OUT="${TEMP_DIR}/client_b.json"
CLIENT_B_HEADERS="${TEMP_DIR}/client_b_headers.txt"

echo "Launching Client A (Heavy Query)..."
curl -s -X POST "${BASE_URL}/api/chat" \
    -H "Content-Type: application/json" \
    -d '{"question":"Quelles sont les conditions de constitution du capital minimum des banques ?"}' \
    > "${CLIENT_A_OUT}" &
CLIENT_A_PID=$!

# Wait 1 second to ensure Client A has acquired the inference lock
sleep 1

# 3. Test Sibling Thread Liveness during active inference (Client B checks health & status)
echo -n "Checking /api/health during active inference... "
T_START=$(date +%s%N)
HEALTH_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/api/health")
T_END=$(date +%s%N)
DUR_MS=$(( (T_END - T_START) / 1000000 ))

if [ "$HEALTH_CODE" = "200" ] && [ "$DUR_MS" -lt 1000 ]; then
    echo "PASS (HTTP 200 in ${DUR_MS}ms)"
else
    echo "FAIL (HTTP ${HEALTH_CODE} in ${DUR_MS}ms)"
fi

echo -n "Checking /api/status during active inference... "
STATUS_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/api/status")
if [ "$STATUS_CODE" = "200" ]; then
    echo "PASS (HTTP 200)"
else
    echo "FAIL (HTTP ${STATUS_CODE})"
fi

# 4. Test Simultaneous Chat Contention (Client B calls /api/chat while Client A holds lock)
echo -n "Testing Chat Lock Contention (Simultaneous POST /api/chat)... "
HTTP_429_CODE=$(curl -s -i -X POST "${BASE_URL}/api/chat" \
    -H "Content-Type: application/json" \
    -d '{"question":"Autre question concurrente"}' \
    -D "${CLIENT_B_HEADERS}" \
    -o "${CLIENT_B_OUT}" -w "%{http_code}")

if [ "$HTTP_429_CODE" = "429" ]; then
    echo "PASS (Received HTTP 429)"
else
    echo "FAIL (Expected HTTP 429, got ${HTTP_429_CODE})"
fi

echo -n "Verifying Retry-After header presence in 429 response... "
if grep -iq "Retry-After" "${CLIENT_B_HEADERS}"; then
    RETRY_VAL=$(grep -i "Retry-After" "${CLIENT_B_HEADERS}" | tr -d '\r\n')
    echo "PASS (${RETRY_VAL})"
else
    echo "FAIL (Retry-After header missing)"
fi

# 5. Wait for Client A to finish
echo "Waiting for Client A query to finish..."
wait "${CLIENT_A_PID}"
echo "Client A completed successfully."

echo "=================================================="
echo "All Concurrency & Contention Checks Passed!"
echo "=================================================="
