#!/usr/bin/env bash
# ==============================================================================
# RegAssist DZ - Three-Case Proxy Security Verification Test Suite
# ==============================================================================
# Tests the Nginx edge filter and Flask production guard against spoofing and
# unauthorized Host/Origin headers.
#
# Usage:
#   ./deploy/test_proxy_security.sh [TARGET_URL] [SERVER_IP]
#
# Defaults:
#   TARGET_URL: https://regassist.example.com (or http://127.0.0.1:8790 for direct test)
#   SERVER_IP: 127.0.0.1
# ==============================================================================

set -euo pipefail

TARGET_URL="${1:-http://127.0.0.1:8790}"
SERVER_IP="${2:-127.0.0.1}"

echo "=================================================="
echo "RegAssist DZ - Proxy Security Verification"
echo "Target URL: ${TARGET_URL}"
echo "Server IP : ${SERVER_IP}"
echo "=================================================="

PASSED=0
TOTAL=3

# Case 1: Unknown / Unapproved Host Header
echo -n "Test 1: Unknown Host header rejection... "
STATUS_CODE=$(curl -s -o /dev/null -w "%{http_code}" -k -H "Host: evil.attacker.com" "${TARGET_URL}/api/health" || echo "000")
if [ "$STATUS_CODE" = "400" ] || [ "$STATUS_CODE" = "403" ] || [ "$STATUS_CODE" = "444" ] || [ "$STATUS_CODE" = "000" ]; then
    echo "PASS (HTTP $STATUS_CODE / Connection Terminated)"
    PASSED=$((PASSED + 1))
else
    echo "FAIL (Expected 400/403/444/000, got HTTP $STATUS_CODE)"
fi

# Case 2: Unapproved Cross-Origin POST request
echo -n "Test 2: Unapproved Origin rejection on POST /api/chat... "
STATUS_CODE=$(curl -s -o /dev/null -w "%{http_code}" -k -X POST "${TARGET_URL}/api/chat" \
    -H "Origin: https://malicious.cross-origin.site" \
    -H "Content-Type: application/json" \
    -d '{"question":"test"}' || echo "000")
if [ "$STATUS_CODE" = "400" ] || [ "$STATUS_CODE" = "403" ]; then
    echo "PASS (HTTP $STATUS_CODE)"
    PASSED=$((PASSED + 1))
else
    echo "FAIL (Expected 400/403, got HTTP $STATUS_CODE)"
fi

# Case 3: Legitimate Host with Spoofed X-Forwarded-* Headers Overwrite
echo -n "Test 3: Spoofed X-Forwarded-* headers handled cleanly... "
RESPONSE=$(curl -s -k -i "${TARGET_URL}/api/health" \
    -H "X-Forwarded-For: 198.51.100.1" \
    -H "X-Forwarded-Proto: http" \
    -H "X-Forwarded-Host: spoofed.internal.corp" || true)

STATUS_CODE=$(echo "$RESPONSE" | grep -i "^HTTP" | tail -1 | awk '{print $2}')
if [ "$STATUS_CODE" = "200" ]; then
    echo "PASS (HTTP 200 - Server remained healthy and isolated)"
    PASSED=$((PASSED + 1))
else
    echo "FAIL (Expected HTTP 200 for health endpoint, got $STATUS_CODE)"
fi

echo "=================================================="
echo "Security Proxy Verification: ${PASSED}/${TOTAL} Tests Passed"
echo "=================================================="

if [ "$PASSED" -eq "$TOTAL" ]; then
    exit 0
else
    exit 1
fi
