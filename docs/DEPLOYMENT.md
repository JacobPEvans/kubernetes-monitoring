# Deployment Guide

## Prerequisites

- OrbStack with Kubernetes enabled
- `kubectl` configured with `orbstack` context
- `sops` and `age` installed (for secret management)
- `kustomize` (bundled with kubectl 1.14+)

## SOPS Setup

1. Ensure your age key is available:

   ```bash
   # Key should be at ~/.config/sops/age/keys.txt
   ls ~/.config/sops/age/keys.txt
   ```

2. Create and encrypt secrets:

   ```bash
   cp secrets.enc.yaml.example secrets.enc.yaml
   sops secrets.enc.yaml
   ```

3. Fill in real values for all secrets.

## Deploy

### Quick Deploy

```bash
sops exec-env secrets.enc.yaml 'make deploy'
```

### Step-by-Step

```bash
# 1. Generate local overlay (replaces PLACEHOLDER_HOME_DIR with real paths)
make generate-overlay

# 2. Validate kustomize output
make validate

# 3. Deploy with secrets injected
sops exec-env secrets.enc.yaml './scripts/deploy.sh'
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
# Re-deploy
sops exec-env secrets.enc.yaml 'make deploy'
```

## Tear Down

```bash
make clean
```

This deletes the entire monitoring namespace and all resources within it.
