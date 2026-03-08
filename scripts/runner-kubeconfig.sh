#!/usr/bin/env bash
# Generate a kubeconfig that works from inside an OrbStack Docker container.
# Uses k8s.orb.local (in the cert's SANs) instead of 127.0.0.1 so TLS verification works.
set -euo pipefail
sed \
  -e 's|https://127.0.0.1:26443|https://k8s.orb.local:26443|g' \
  ~/.kube/config
