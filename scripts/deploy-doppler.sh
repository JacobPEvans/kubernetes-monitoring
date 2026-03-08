#!/usr/bin/env bash
# deploy-doppler.sh - Deploy with Cribl secrets from Doppler
#
# Expects DOPPLER_PROJECT and DOPPLER_CONFIG from SOPS (or environment).
# Passes all SOPS env vars through to deploy.sh alongside Doppler secrets.
set -euo pipefail

if [ -z "${DOPPLER_PROJECT:-}" ] || [ -z "${DOPPLER_CONFIG:-}" ]; then
  echo "ERROR: DOPPLER_PROJECT and DOPPLER_CONFIG must be set"
  echo "Add them to secrets.enc.yaml: sops secrets.enc.yaml"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# When DOPPLER_TOKEN is set (CI/non-interactive use), use an isolated config dir so doppler
# reads the token from env without attempting keyring access (which fails in headless containers).
DOPPLER_OPTS=()
if [ -n "${DOPPLER_TOKEN:-}" ]; then
  _DOPPLER_TMP_CFG=$(mktemp -d)
  DOPPLER_OPTS=(--config-dir "$_DOPPLER_TMP_CFG")
fi

# Fetch MCP secrets from cloud-secrets project (CRIBL_BASE_URL, CRIBL_CLIENT_ID, CRIBL_CLIENT_SECRET).
# These supplement the main iac-conf-mgmt secrets (which provide DEFAULT_PASSWORD → MCP_API_KEY).
eval "$(doppler "${DOPPLER_OPTS[@]}" secrets download --project "${CRIBL_MCP_DOPPLER_PROJECT:-cloud-secrets}" --config "${CRIBL_MCP_DOPPLER_CONFIG:-prd}" --format env --no-file 2>/dev/null)" || true

doppler "${DOPPLER_OPTS[@]}" run --project "$DOPPLER_PROJECT" --config "$DOPPLER_CONFIG" -- "$SCRIPT_DIR/deploy.sh"
