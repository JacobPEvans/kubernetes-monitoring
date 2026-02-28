#!/usr/bin/env bash
# deploy.sh - Deploy monitoring stack to OrbStack Kubernetes
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
CONTEXT="${KUBE_CONTEXT:-orbstack}"
NAMESPACE="monitoring"

echo "=== Kubernetes Monitoring Deployment ==="
echo "Context: $CONTEXT"
echo "Namespace: $NAMESPACE"
echo ""

# Step 1: Generate overlay
echo "--- Step 1: Generating overlay ---"
"$SCRIPT_DIR/generate-overlay.sh"
echo ""

# Step 2: Create secrets
echo "--- Step 2: Creating secrets ---"

# Cribl Cloud config (edge master URL)
# Supports: CRIBL_DIST_MASTER_URL (Doppler) or CRIBL_CLOUD_MASTER_URL (SOPS)
CRIBL_EDGE_MASTER="${CRIBL_DIST_MASTER_URL:-${CRIBL_CLOUD_MASTER_URL:-}}"
CLOUD_ARGS=()
[ -n "$CRIBL_EDGE_MASTER" ] && CLOUD_ARGS+=(--from-literal=master-url="$CRIBL_EDGE_MASTER")
if [ ${#CLOUD_ARGS[@]} -gt 0 ]; then
  kubectl --context "$CONTEXT" create secret generic cribl-cloud-config \
    --namespace "$NAMESPACE" \
    "${CLOUD_ARGS[@]}" \
    --dry-run=client -o yaml | kubectl --context "$CONTEXT" apply -f -
  echo "  Created: cribl-cloud-config"
else
  echo "  SKIPPED: cribl-cloud-config (no Cribl master URLs configured)"
  echo "           Set CRIBL_DIST_MASTER_URL or CRIBL_CLOUD_MASTER_URL, or use: make deploy-doppler"
fi

# Cribl Stream admin password
if [ -n "${CRIBL_STREAM_PASSWORD:-}" ]; then
  kubectl --context "$CONTEXT" create secret generic cribl-stream-admin \
    --namespace "$NAMESPACE" \
    --from-literal=password="$CRIBL_STREAM_PASSWORD" \
    --dry-run=client -o yaml | kubectl --context "$CONTEXT" apply -f -
  echo "  Created: cribl-stream-admin"
else
  echo "  SKIPPED: cribl-stream-admin (CRIBL_STREAM_PASSWORD not set)"
fi

# Cribl Edge standalone admin password
if [ -n "${CRIBL_EDGE_PASSWORD:-}" ]; then
  kubectl --context "$CONTEXT" create secret generic cribl-edge-admin \
    --namespace "$NAMESPACE" \
    --from-literal=password="$CRIBL_EDGE_PASSWORD" \
    --dry-run=client -o yaml | kubectl --context "$CONTEXT" apply -f -
  echo "  Created: cribl-edge-admin"
else
  echo "  SKIPPED: cribl-edge-admin (CRIBL_EDGE_PASSWORD not set, using default)"
fi

# Splunk HEC config (standalone edge)
# Derive HEC URL from SPLUNK_NETWORK terraform output (JSON array, e.g. '["192.168.0.200"]')
SPLUNK_HEC_URL=""
if [ -n "${SPLUNK_NETWORK:-}" ]; then
  SPLUNK_IP=$(python3 -c "import json,sys; print(json.loads(sys.argv[1])[0])" "$SPLUNK_NETWORK" 2>/dev/null || { echo "  WARNING: Failed to parse SPLUNK_NETWORK JSON: '$SPLUNK_NETWORK'" >&2; true; })
  # Use direct IP — OrbStack's host.orb.internal proxy strips Authorization headers,
  # causing 403 "Invalid token" on all authenticated POSTs.
  [ -n "$SPLUNK_IP" ] && SPLUNK_HEC_URL="https://${SPLUNK_IP}:8088/services/collector"
fi
if [ -n "${SPLUNK_HEC_TOKEN:-}" ]; then
  HEC_ARGS=(--from-literal=token="$SPLUNK_HEC_TOKEN")
  [ -n "$SPLUNK_HEC_URL" ] && HEC_ARGS+=(--from-literal=url="$SPLUNK_HEC_URL")
  # Add management API URL and password for test queries (requires SPLUNK_NETWORK and SPLUNK_PASSWORD)
  [ -n "${SPLUNK_IP:-}" ] && HEC_ARGS+=(--from-literal=mgmt-url="https://${SPLUNK_IP}:8089")
  [ -n "${SPLUNK_PASSWORD:-}" ] && HEC_ARGS+=(--from-literal=admin-password="$SPLUNK_PASSWORD")
  kubectl --context "$CONTEXT" create secret generic splunk-hec-config \
    --namespace "$NAMESPACE" \
    "${HEC_ARGS[@]}" \
    --dry-run=client -o yaml | kubectl --context "$CONTEXT" apply -f -
  echo "  Created: splunk-hec-config (url derived from SPLUNK_NETWORK: ${SPLUNK_HEC_URL:-not set})"
else
  echo "  SKIPPED: splunk-hec-config (SPLUNK_HEC_TOKEN not set)"
fi

# AI API keys
if [ -n "${CLAUDE_API_KEY:-}" ] || [ -n "${GEMINI_API_KEY:-}" ]; then
  ARGS=()
  [ -n "${CLAUDE_API_KEY:-}" ] && ARGS+=(--from-literal=claude-api-key="$CLAUDE_API_KEY")
  [ -n "${GEMINI_API_KEY:-}" ] && ARGS+=(--from-literal=gemini-api-key="$GEMINI_API_KEY")
  kubectl --context "$CONTEXT" create secret generic ai-api-keys \
    --namespace "$NAMESPACE" \
    "${ARGS[@]}" \
    --dry-run=client -o yaml | kubectl --context "$CONTEXT" apply -f -
  echo "  Created: ai-api-keys"
else
  echo "  SKIPPED: ai-api-keys (no API keys set)"
fi

# Heartbeat config (healthchecks.io ping URLs from SOPS)
HB_ARGS=()
[ -n "${HEALTHCHECKS_STREAM_URL:-}" ] && HB_ARGS+=(--from-literal=stream-url="$HEALTHCHECKS_STREAM_URL")
[ -n "${HEALTHCHECKS_SPLUNK_URL:-}" ] && HB_ARGS+=(--from-literal=splunk-url="$HEALTHCHECKS_SPLUNK_URL")
[ -n "${HEALTHCHECKS_EDGE_URL:-}" ] && HB_ARGS+=(--from-literal=edge-url="$HEALTHCHECKS_EDGE_URL")
[ -n "${HEALTHCHECKS_OTEL_URL:-}" ] && HB_ARGS+=(--from-literal=otel-url="$HEALTHCHECKS_OTEL_URL")
if [ ${#HB_ARGS[@]} -gt 0 ]; then
  kubectl --context "$CONTEXT" create secret generic heartbeat-config \
    --namespace "$NAMESPACE" \
    "${HB_ARGS[@]}" \
    --dry-run=client -o yaml | kubectl --context "$CONTEXT" apply -f -
  echo "  Created: heartbeat-config"
else
  echo "  SKIPPED: heartbeat-config (no HEALTHCHECKS_*_URL set)"
fi

# Cribl MCP server config (CRIBL_BASE_URL from cloud-secrets, MCP_API_KEY from iac-conf-mgmt DEFAULT_PASSWORD)
MCP_BASE_URL="${CRIBL_BASE_URL:-}"
if [ -n "$MCP_BASE_URL" ]; then
  MCP_ARGS=(--from-literal=base-url="$MCP_BASE_URL")
  [ -n "${CRIBL_CLIENT_ID:-}" ] && MCP_ARGS+=(--from-literal=client-id="$CRIBL_CLIENT_ID")
  [ -n "${CRIBL_CLIENT_SECRET:-}" ] && MCP_ARGS+=(--from-literal=client-secret="$CRIBL_CLIENT_SECRET")
  [ -n "${DEFAULT_PASSWORD:-}" ] && MCP_ARGS+=(--from-literal=api-key="$DEFAULT_PASSWORD")
  kubectl --context "$CONTEXT" create secret generic cribl-mcp-config \
    --namespace "$NAMESPACE" \
    "${MCP_ARGS[@]}" \
    --dry-run=client -o yaml | kubectl --context "$CONTEXT" apply -f -
  echo "  Created: cribl-mcp-config"
else
  echo "  SKIPPED: cribl-mcp-config (CRIBL_BASE_URL not set)"
  echo "           Set CRIBL_BASE_URL in Doppler cloud-secrets/prd, or use: make deploy-doppler"
fi
echo ""

# Step 3: Apply kustomize
echo "--- Step 3: Applying kustomize overlay ---"
kubectl --context "$CONTEXT" apply -k "$REPO_ROOT/k8s/overlays/local/"
echo ""

# Step 3.5: Restart all StatefulSets to pick up any ConfigMap/Secret changes.
# Kubernetes does not restart pods automatically when ConfigMaps or Secrets change,
# so we force a rolling restart on every deploy to guarantee consistency.
echo "--- Step 3.5: Restarting StatefulSets ---"
kubectl --context "$CONTEXT" -n "$NAMESPACE" rollout restart \
  statefulset/otel-collector \
  statefulset/cribl-edge-standalone \
  statefulset/cribl-stream-standalone \
  statefulset/cribl-edge-managed \
  statefulset/cribl-mcp-server
echo ""

# Step 4: Wait for rollouts
echo "--- Step 4: Waiting for rollouts ---"
declare -A timeouts=(
  [otel-collector]=120s
  [cribl-edge-managed]=120s
  # 420s: startupProbe max (10s + 30×10s = 310s) + postStart setup-edge.sh (MAX_RETRIES=150, 2s sleep = 300s max)
  # The postStart hook runs concurrently with the startupProbe; 420s gives ample margin for cold starts.
  [cribl-edge-standalone]=420s
  # 300s accounts for PVC provisioning + startupProbe (30 failures × 10s = 300s max)
  [cribl-stream-standalone]=300s
  [cribl-mcp-server]=120s
)

for name in otel-collector cribl-edge-managed cribl-edge-standalone cribl-stream-standalone cribl-mcp-server; do
  kubectl --context "$CONTEXT" -n "$NAMESPACE" rollout status "statefulset/$name" --timeout="${timeouts[$name]}"
done
echo ""

# Step 5: Print endpoints
echo "=== Deployment Complete ==="
echo ""
echo "Service Endpoints:"
echo "  OTEL gRPC:                   localhost:30317"
echo "  OTEL HTTP:                   localhost:30318"
echo "  Cribl Stream Standalone UI:  http://localhost:30900  (admin / CRIBL_STREAM_PASSWORD)"
echo "  Cribl Edge Standalone UI:    http://localhost:30910"
echo "  Cribl MCP Server:            http://localhost:30030/mcp"
echo ""
echo "Verify:"
echo "  kubectl --context $CONTEXT get all -n $NAMESPACE"
