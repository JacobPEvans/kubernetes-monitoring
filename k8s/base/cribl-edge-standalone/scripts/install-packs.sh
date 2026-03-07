#!/bin/sh
# Install Edge packs via Cribl REST API. Using the API instead of manual
# download/extract/merge eliminates the duplicated curl+tar+rm pattern per pack.
set -eu

API="http://127.0.0.1:9420/api/v1"

# Wait up to 10 minutes for Cribl to accept API requests.
i=0
until curl -sf "${API}/health" >/dev/null 2>&1; do
  i=$((i+1)); [ "$i" -gt 120 ] && echo "Cribl not ready after 10min" && exit 0
  sleep 5
done

TOKEN=$(curl -sf -X POST "${API}/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"admin\",\"password\":\"${CRIBL_EDGE_PASSWORD:-admin}\"}" \
  | grep -o '"token":"[^"]*"' | cut -d'"' -f4)
[ -z "$TOKEN" ] && echo "WARNING: Auth failed, skipping pack install" && exit 0

PACK_CLAUDE="https://github.com/JacobPEvans/cc-edge-claude-code-otel/releases/download/v2.0.0/cc-edge-claude-code-otel.crbl"
PACK_GEMINI="https://github.com/JacobPEvans/cc-edge-gemini-antigravity-io/releases/download/v0.1.0/cc-edge-gemini-antigravity-io.crbl"

# Install each pack only if not already present (idempotent across pod restarts).
if ! curl -sf -H "Authorization: Bearer ${TOKEN}" "${API}/packs/cc-edge-claude-code" >/dev/null 2>&1; then
  curl -sf -X POST "${API}/packs" -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"cc-edge-claude-code\",\"source\":\"${PACK_CLAUDE}\"}" \
    || echo "WARNING: Claude pack install failed"
fi

# Cribl auto-disables gemini-cli-otel (port 4317 conflict with claude-code-otel).
if ! curl -sf -H "Authorization: Bearer ${TOKEN}" "${API}/packs/cc-edge-gemini" >/dev/null 2>&1; then
  curl -sf -X POST "${API}/packs" -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"cc-edge-gemini\",\"source\":\"${PACK_GEMINI}\"}" \
    || echo "WARNING: Gemini pack install failed"
fi

# Edge 4.16.x bug: FileMonitor ignores patterns not starting with '*'.
# Patch session-*.json (star in middle) to *.json after pack writes the file.
EDGE_DIR="${CRIBL_VOLUME_DIR}/local/edge"
sed -i 's/"session-\*\.json"/"*.json"/' "${EDGE_DIR}/inputs.yml" 2>/dev/null || true

echo "Pack installation complete"
