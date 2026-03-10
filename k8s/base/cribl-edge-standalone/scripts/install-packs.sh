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

PACK_CLAUDE="https://github.com/JacobPEvans/cc-edge-claude-code-otel/releases/download/v1.2.4/cc-edge-claude-code-otel.crbl"
PACK_GEMINI="https://github.com/JacobPEvans/cc-edge-gemini-antigravity-io/releases/download/v1.1.1/cc-edge-gemini-antigravity-io.crbl"

# Install each pack only if not already present (idempotent across pod restarts).
# Each pack install triggers a Cribl worker reload. We must wait for the reload
# to complete before installing the next pack, otherwise the second install
# happens during the first reload and the worker never loads the second pack
# until the next file-change-triggered reload (which can be minutes later).
if ! curl -sf -H "Authorization: Bearer ${TOKEN}" "${API}/packs/cc-edge-claude-code" >/dev/null 2>&1; then
  curl -sf -X POST "${API}/packs" -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"cc-edge-claude-code\",\"source\":\"${PACK_CLAUDE}\"}" \
    || echo "WARNING: Claude pack install failed"
  # Wait for Cribl worker to finish reloading after Claude pack install.
  sleep 10
fi

# Cribl auto-disables gemini-cli-otel (port 4317 conflict with claude-code-otel).
if ! curl -sf -H "Authorization: Bearer ${TOKEN}" "${API}/packs/cc-edge-gemini-antigravity" >/dev/null 2>&1; then
  curl -sf -X POST "${API}/packs" -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"cc-edge-gemini\",\"source\":\"${PACK_GEMINI}\"}" \
    || echo "WARNING: Gemini pack install failed"
  # Wait for Cribl worker to finish reloading after Gemini pack install.
  sleep 10
fi

# Force Cribl to commit all pending config changes and reload the worker.
# Note: "effective" param requires a group and fails on Edge standalone,
# so we use version/commit (without effective) + system/settings/reload.
curl -sf -X POST "${API}/version/commit" -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"message":"Pack installation"}' \
  || echo "WARNING: version/commit failed, worker may not have loaded config changes"
curl -sf -X POST "${API}/system/settings/reload" \
  -H "Authorization: Bearer ${TOKEN}" \
  || echo "WARNING: settings reload failed, worker may not have loaded new packs"

echo "Pack installation complete"
