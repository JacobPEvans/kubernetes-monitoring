# Deployment Guide

## Prerequisites

- OrbStack with Kubernetes enabled
- `kubectl` configured with `orbstack` context
- `doppler` CLI authenticated (`doppler login`) for Cribl secrets
- `sops` and `age` installed (for secret management)
- `kustomize` (bundled with kubectl 1.14+)

## Secret Management

All secrets are stored in SOPS-encrypted `secrets.enc.yaml`, including the Doppler project/config used to fetch Cribl secrets at deploy time.

| Secret | Purpose |
|--------|---------|
| `DOPPLER_PROJECT` | Doppler project name (for Cribl secrets) |
| `DOPPLER_CONFIG` | Doppler config name (for Cribl secrets) |
| `CRIBL_CLOUD_MASTER_URL` | Alternative: direct Cribl Edge URL (if not using Doppler) |
| `CRIBL_STREAM_PASSWORD` | Cribl Stream standalone admin password |
| `SPLUNK_HEC_TOKEN` | Splunk HEC token (standalone edge to Splunk) |
| `SPLUNK_NETWORK` | Splunk IP(s) from terraform output (JSON array, e.g. `["192.168.0.200"]`). HEC URL is derived automatically at deploy time. |
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

This reads Doppler project/config from SOPS, fetches Cribl secrets (including `CRIBL_DIST_MASTER_URL`) via Doppler, and deploys the full stack.

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

## Cribl Stream

- **cribl-stream-standalone**: Local leader with UI at <http://localhost:30900> (admin / `CRIBL_STREAM_PASSWORD`)

## OTLP Telemetry

The OTEL Collector forwards telemetry via gRPC to `cribl-edge-managed:4317`. The managed edge fleet has an `open_telemetry` source configured with `host: 0.0.0.0`, `port: 4317`, `protocol: grpc` in Cribl Cloud.

## Verify

```bash
# Check all pods are Running
make status

# Check OTEL Collector health
kubectl exec -n monitoring statefulset/otel-collector -- curl -s http://localhost:13133/

# Check Cribl Edge managed logs
kubectl logs -n monitoring statefulset/cribl-edge-managed --tail=10

# Check Cribl Edge standalone UI
open http://localhost:30910

# Check Cribl Stream standalone UI
open http://localhost:30900

# Verify OTEL can reach managed edge OTLP source
kubectl exec -n monitoring statefulset/otel-collector -- curl -sf http://cribl-edge-managed:4317
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
