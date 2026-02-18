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

# Cribl Cloud config (edge + stream master URLs)
# Supports: CRIBL_DIST_MASTER_URL (Doppler) or CRIBL_CLOUD_MASTER_URL (SOPS)
CRIBL_EDGE_MASTER="${CRIBL_DIST_MASTER_URL:-${CRIBL_CLOUD_MASTER_URL:-}}"
CRIBL_STREAM_MASTER="${CRIBL_STREAM_MASTER_URL:-}"
CLOUD_ARGS=()
[ -n "$CRIBL_EDGE_MASTER" ] && CLOUD_ARGS+=(--from-literal=master-url="$CRIBL_EDGE_MASTER")
[ -n "$CRIBL_STREAM_MASTER" ] && CLOUD_ARGS+=(--from-literal=stream-master-url="$CRIBL_STREAM_MASTER")
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

# Splunk HEC config (standalone edge)
if [ -n "${SPLUNK_HEC_TOKEN:-}" ]; then
  HEC_ARGS=(--from-literal=token="$SPLUNK_HEC_TOKEN")
  [ -n "${SPLUNK_HEC_URL:-}" ] && HEC_ARGS+=(--from-literal=url="$SPLUNK_HEC_URL")
  kubectl --context "$CONTEXT" create secret generic splunk-hec-config \
    --namespace "$NAMESPACE" \
    "${HEC_ARGS[@]}" \
    --dry-run=client -o yaml | kubectl --context "$CONTEXT" apply -f -
  echo "  Created: splunk-hec-config"
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
echo ""

# Step 3: Clean up old cribl-stream resources (replaced by standalone + managed)
# Must run before apply to free NodePort 30900 for cribl-stream-standalone-ui
echo "--- Step 3: Cleaning up old cribl-stream deployment ---"
if kubectl --context "$CONTEXT" -n "$NAMESPACE" delete deployment cribl-stream 2>/dev/null; then
  echo "  Deleted: deployment/cribl-stream"
fi
if kubectl --context "$CONTEXT" -n "$NAMESPACE" delete service cribl-stream cribl-stream-ui 2>/dev/null; then
  echo "  Deleted: service/cribl-stream, service/cribl-stream-ui"
fi
echo ""

# Step 4: Apply kustomize
echo "--- Step 4: Applying kustomize overlay ---"
kubectl --context "$CONTEXT" apply -k "$REPO_ROOT/k8s/overlays/local/"
echo ""

# Step 5: Wait for rollouts
echo "--- Step 5: Waiting for rollouts ---"
kubectl --context "$CONTEXT" -n "$NAMESPACE" rollout status deployment/otel-collector --timeout=120s || true
kubectl --context "$CONTEXT" -n "$NAMESPACE" rollout status deployment/cribl-edge-managed --timeout=120s || true
kubectl --context "$CONTEXT" -n "$NAMESPACE" rollout status deployment/cribl-edge-standalone --timeout=120s || true
kubectl --context "$CONTEXT" -n "$NAMESPACE" rollout status deployment/cribl-stream-standalone --timeout=180s || true
kubectl --context "$CONTEXT" -n "$NAMESPACE" rollout status deployment/cribl-stream-managed --timeout=120s || true
echo ""

# Step 6: Print endpoints
echo "=== Deployment Complete ==="
echo ""
echo "Service Endpoints:"
echo "  OTEL gRPC:                   localhost:30317"
echo "  OTEL HTTP:                   localhost:30318"
echo "  Cribl Stream Standalone UI:  http://localhost:30900  (admin / CRIBL_STREAM_PASSWORD)"
echo "  Cribl Edge Standalone UI:    http://localhost:30910"
echo ""
echo "Note: cribl-stream-managed has no UI (cloud-managed worker)."
echo ""
echo "Verify:"
echo "  kubectl --context $CONTEXT get all -n $NAMESPACE"
