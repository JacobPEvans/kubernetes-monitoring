# Deployment Guide

## Prerequisites

- OrbStack with Kubernetes enabled
- `kubectl` configured with `orbstack` context
- `doppler` CLI configured (for Cribl secrets)
- `sops` and `age` installed (for secret management)
- `kustomize` (bundled with kubectl 1.14+)

## Secret Management

All secrets are stored in SOPS-encrypted `secrets.enc.yaml`, including the Doppler project/config used to fetch Cribl secrets at deploy time.

| Secret | Purpose |
|--------|---------|
| `DOPPLER_PROJECT` | Doppler project name (for Cribl secrets) |
| `DOPPLER_CONFIG` | Doppler config name (for Cribl secrets) |
| `CRIBL_CLOUD_MASTER_URL` | Alternative: direct Cribl URL (if not using Doppler) |
| `CRIBL_STREAM_PASSWORD` | Cribl Stream admin password |
| `CLAUDE_API_KEY` | AI container API key |
| `GEMINI_API_KEY` | AI container API key |

### SOPS Setup (one-time)

```bash
# Ensure your age key exists
ls ~/.config/sops/age/keys.txt

# Create and encrypt secrets
cp secrets.enc.yaml.example secrets.enc.yaml
sops secrets.enc.yaml
```

## Deploy

### Quick Deploy (Doppler + SOPS)

```bash
make deploy-doppler
```

This reads Doppler project/config from SOPS, fetches Cribl secrets via Doppler, and deploys the full stack.

### Deploy Without Doppler

If Cribl secrets are set directly in `secrets.enc.yaml` (via `CRIBL_CLOUD_MASTER_URL`):

```bash
sops exec-env secrets.enc.yaml 'make deploy'
```

### Step-by-Step

```bash
# 1. Generate local overlay (replaces PLACEHOLDER_HOME_DIR with real paths)
make generate-overlay

# 2. Validate kustomize output
make validate

# 3. Deploy with secrets
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
