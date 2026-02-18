# Deployment Guide

## Prerequisites

- OrbStack with Kubernetes enabled
- `kubectl` configured with `orbstack` context
- `doppler` CLI configured (for Cribl secrets)
- `sops` and `age` installed (for AI API keys, optional)
- `kustomize` (bundled with kubectl 1.14+)

## Secret Sources

| Secret | Source | Doppler Project/Config |
|--------|--------|------------------------|
| `CRIBL_DIST_MASTER_URL` | Doppler | `iac-conf-mgmt/prd` |
| `CRIBL_TOKEN` | Doppler | `iac-conf-mgmt/prd` |
| `CLAUDE_API_KEY` | SOPS or manual | N/A |
| `GEMINI_API_KEY` | SOPS or manual | N/A |

## Deploy

### Quick Deploy (Doppler)

```bash
make deploy-doppler
```

This runs `doppler run --project iac-conf-mgmt --config prd -- ./scripts/deploy.sh`, injecting Cribl secrets automatically.

### With SOPS (for AI keys)

```bash
# Set up SOPS secrets (one-time)
cp secrets.enc.yaml.example secrets.enc.yaml
sops secrets.enc.yaml

# Deploy with both Doppler + SOPS
doppler run --project iac-conf-mgmt --config prd -- sops exec-env secrets.enc.yaml './scripts/deploy.sh'
```

### Step-by-Step

```bash
# 1. Generate local overlay (replaces PLACEHOLDER_HOME_DIR with real paths)
make generate-overlay

# 2. Validate kustomize output
make validate

# 3. Deploy with Doppler secrets
make deploy-doppler
```

## Verify

```bash
# Check all pods are Running
make status

# Check OTEL Collector health
kubectl exec -n monitoring deploy/otel-collector -- curl -s http://localhost:13133/

# Check Cribl Edge managed logs for pack
kubectl logs -n monitoring deploy/cribl-edge-managed | grep -i pack

# Check Cribl Edge standalone UI
open http://localhost:30910

# Check Cribl Stream UI
open http://localhost:30900
```

## Update

After modifying base manifests:

```bash
make deploy-doppler
```

## Tear Down

```bash
make clean
```

This deletes the entire monitoring namespace and all resources within it.
