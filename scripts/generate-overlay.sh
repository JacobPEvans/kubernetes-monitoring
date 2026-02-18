#!/usr/bin/env bash
# generate-overlay.sh - Generate local kustomize overlay with real volume paths
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
OVERLAY_DIR="$REPO_ROOT/k8s/overlays/local"
PATCHES_DIR="$OVERLAY_DIR/patches"
HOME_DIR="$HOME"

echo "Generating local overlay..."
echo "  HOME: $HOME_DIR"
echo "  Output: $OVERLAY_DIR"

# Clean and recreate
rm -rf "$OVERLAY_DIR"
mkdir -p "$PATCHES_DIR"

# Main kustomization.yaml
cat > "$OVERLAY_DIR/kustomization.yaml" << EOF
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

patches:
  - path: patches/otel-volumes.yaml
  - path: patches/cribl-managed-volumes.yaml
  - path: patches/cribl-standalone-volumes.yaml
EOF

# OTEL Collector volume patch
cat > "$PATCHES_DIR/otel-volumes.yaml" << EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: otel-collector
  namespace: monitoring
spec:
  template:
    spec:
      volumes:
        - name: config
          configMap:
            name: otel-collector-config
        - name: claude-logs
          hostPath:
            path: ${HOME_DIR}/.claude/logs
            type: DirectoryOrCreate
        - name: ai-job-logs
          hostPath:
            path: ${HOME_DIR}/logs/ai-jobs
            type: DirectoryOrCreate
EOF

# Cribl Edge Managed volume patch
cat > "$PATCHES_DIR/cribl-managed-volumes.yaml" << EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cribl-edge-managed
  namespace: monitoring
spec:
  template:
    spec:
      volumes:
        - name: claude-logs
          hostPath:
            path: ${HOME_DIR}/.claude
            type: DirectoryOrCreate
        - name: ollama-logs
          hostPath:
            path: ${HOME_DIR}/Library/Logs/Ollama
            type: DirectoryOrCreate
        - name: terminal-logs
          hostPath:
            path: ${HOME_DIR}/logs
            type: DirectoryOrCreate
        - name: ai-job-logs
          hostPath:
            path: ${HOME_DIR}/logs/ai-jobs
            type: DirectoryOrCreate
EOF

# Cribl Edge Standalone volume patch
cat > "$PATCHES_DIR/cribl-standalone-volumes.yaml" << EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cribl-edge-standalone
  namespace: monitoring
spec:
  template:
    spec:
      volumes:
        - name: claude-logs
          hostPath:
            path: ${HOME_DIR}/.claude
            type: DirectoryOrCreate
        - name: ollama-logs
          hostPath:
            path: ${HOME_DIR}/Library/Logs/Ollama
            type: DirectoryOrCreate
        - name: terminal-logs
          hostPath:
            path: ${HOME_DIR}/logs
            type: DirectoryOrCreate
        - name: ai-job-logs
          hostPath:
            path: ${HOME_DIR}/logs/ai-jobs
            type: DirectoryOrCreate
        - name: cribl-config
          configMap:
            name: cribl-edge-standalone-config
EOF

echo "Overlay generated successfully."
