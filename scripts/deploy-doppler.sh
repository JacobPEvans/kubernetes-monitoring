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

# Fetch MCP secrets from cloud-secrets project (CRIBL_BASE_URL, CRIBL_CLIENT_ID, CRIBL_CLIENT_SECRET).
# These supplement the main iac-conf-mgmt secrets (which provide DEFAULT_PASSWORD → MCP_API_KEY).
eval "$(doppler secrets download --project cloud-secrets --config prd --format env --no-file 2>/dev/null)" || true

doppler run --project "$DOPPLER_PROJECT" --config "$DOPPLER_CONFIG" -- "$SCRIPT_DIR/deploy.sh"
