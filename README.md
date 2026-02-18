# kubernetes-monitoring

Kubernetes monitoring stack for local OrbStack cluster. Collects, processes, and routes logs from Claude Code, Ollama, terminal sessions, and ephemeral AI containers.

## Components

| Component | Purpose | Ports |
|-----------|---------|-------|
| OTEL Collector | Telemetry collection (traces, metrics, logs) | 4317 (gRPC), 4318 (HTTP), 30317/30318 (NodePort) |
| Cribl Edge (Managed) | Log collection, connected to Cribl Cloud | 9420 (OTEL), 9000 (UI) |
| Cribl Edge (Standalone) | Local log collection, independent | 9420 (OTEL), 30910 (UI NodePort) |
| Cribl Stream | Log routing and transformation | 9000 (API), 30900 (UI NodePort) |
| AI Jobs | Ephemeral Claude Code / Gemini CLI containers | N/A |

## Quick Start

```bash
# 1. Clone and enter repo
cd ~/git/kubernetes-monitoring/main

# 2. Set up secrets (one-time)
cp secrets.enc.yaml.example secrets.enc.yaml
sops secrets.enc.yaml

# 3. Deploy (Doppler exports CRIBL_DIST_MASTER_URL, project/config in SOPS)
make deploy-doppler

# 4. Verify
make status
```

## Architecture

```text
                    ┌──────────────────────┐
                    │     macOS Host        │
                    │                       │
                    │  ~/.claude/logs/      │
                    │  ~/Library/Logs/      │
                    │  ~/logs/              │
                    └──────────┬───────────┘
                               │ hostPath mounts
                    ┌──────────▼───────────┐
                    │   OrbStack Cluster    │
                    │   (monitoring ns)     │
                    │                       │
  ┌─────────────┐   │  ┌───────────────┐   │
  │ Claude Code ├───┼─►│ OTEL Collector├───┼──►  Cribl Edge
  │ (OTLP SDK)  │   │  └───────────────┘   │    (Managed)
  └─────────────┘   │                       │        │
                    │  ┌───────────────┐   │        ▼
                    │  │ Cribl Edge    │   │   Cribl Cloud
                    │  │ (Standalone)  │   │
                    │  └───────┬───────┘   │
                    │          │            │
                    │  ┌───────▼───────┐   │
                    │  │ Cribl Stream  │   │
                    │  │ (Local)       │   │
                    │  └───────────────┘   │
                    └──────────────────────┘
```

## Directory Structure

```text
kubernetes-monitoring/
├── k8s/
│   ├── base/                    # Kustomize base (portable, no real paths)
│   │   ├── kustomization.yaml
│   │   ├── namespace.yaml
│   │   ├── priority-classes.yaml
│   │   ├── otel-collector/
│   │   ├── cribl-edge-managed/
│   │   ├── cribl-edge-standalone/
│   │   ├── cribl-stream/
│   │   └── ai-jobs/
│   └── overlays/
│       └── local/               # Generated at deploy time (gitignored)
├── docker/
│   ├── claude-code/             # Ephemeral Claude Code container
│   └── gemini-cli/              # Ephemeral Gemini CLI container
├── scripts/
│   ├── deploy.sh                # Full deployment script
│   └── generate-overlay.sh      # Overlay generator
├── packs/                       # Cribl Edge pack files
├── docs/                        # Extended documentation
└── Makefile
```

## Make Targets

| Target | Description |
|--------|-------------|
| `make help` | Show all targets |
| `make validate` | Validate kustomize builds cleanly |
| `make deploy` | Full deploy (generate overlay + secrets + apply) |
| `make deploy-doppler` | Deploy with Cribl secrets from Doppler |
| `make status` | Show pod status |
| `make logs` | Tail all pod logs |
| `make build-images` | Build Docker images |
| `make clean` | Delete monitoring namespace |

## Documentation

- [Deployment Guide](docs/DEPLOYMENT.md)
- [Troubleshooting](docs/TROUBLESHOOTING.md)
- [AI Containers](docs/AI-CONTAINERS.md)
