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

# Cribl Cloud config (managed edge)
# Supports: CRIBL_DIST_MASTER_URL (Doppler) or CRIBL_CLOUD_MASTER_URL (SOPS)
CRIBL_MASTER="${CRIBL_DIST_MASTER_URL:-${CRIBL_CLOUD_MASTER_URL:-}}"
if [ -n "$CRIBL_MASTER" ]; then
  kubectl --context "$CONTEXT" create secret generic cribl-cloud-config \
    --namespace "$NAMESPACE" \
    --from-literal=master-url="$CRIBL_MASTER" \
    --dry-run=client -o yaml | kubectl --context "$CONTEXT" apply -f -
  echo "  Created: cribl-cloud-config"
else
  echo "  SKIPPED: cribl-cloud-config (CRIBL_DIST_MASTER_URL not set)"
  echo "           Run: make deploy-doppler"
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

# Step 3: Apply kustomize
echo "--- Step 3: Applying kustomize overlay ---"
kubectl --context "$CONTEXT" apply -k "$REPO_ROOT/k8s/overlays/local/"
echo ""

# Step 4: Wait for rollouts
echo "--- Step 4: Waiting for rollouts ---"
kubectl --context "$CONTEXT" -n "$NAMESPACE" rollout status deployment/otel-collector --timeout=120s || true
kubectl --context "$CONTEXT" -n "$NAMESPACE" rollout status deployment/cribl-edge-managed --timeout=120s || true
kubectl --context "$CONTEXT" -n "$NAMESPACE" rollout status deployment/cribl-edge-standalone --timeout=120s || true
kubectl --context "$CONTEXT" -n "$NAMESPACE" rollout status deployment/cribl-stream --timeout=120s || true
echo ""

# Step 5: Print endpoints
echo "=== Deployment Complete ==="
echo ""
echo "Service Endpoints:"
echo "  OTEL gRPC:              localhost:30317"
echo "  OTEL HTTP:              localhost:30318"
echo "  Cribl Stream UI:        http://localhost:30900"
echo "  Cribl Edge Standalone:  http://localhost:30910"
echo ""
echo "Verify:"
echo "  kubectl --context $CONTEXT get all -n $NAMESPACE"
