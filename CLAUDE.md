# kubernetes-monitoring

Kubernetes monitoring manifests for local OrbStack cluster.

## Architecture Invariant

**Edge → Stream → Splunk is the ONLY allowed data path.**

- `cribl-edge-standalone` sends ONLY to `cribl-stream-standalone` (HEC port 8088). It MUST NOT talk directly to Splunk.
- `cribl-stream-standalone` is the ONLY component with Splunk egress.
- Network policies enforce this: edge egress is locked to stream:8088 only.

## Key Rules

- **PLACEHOLDER_HOME_DIR**: Base manifests use literal `PLACEHOLDER_HOME_DIR` for hostPath volumes. NEVER replace with real paths in `k8s/base/`.
- **Overlays are gitignored**: `k8s/overlays/local/` is generated at deploy time by `scripts/generate-overlay.sh` and must not be committed.
- **Deploy workflow**: `make deploy` generates overlay + creates secrets + applies kustomize.
- **Secrets**: All secrets in SOPS (`secrets.enc.yaml`). Doppler project/config stored in SOPS, never hardcoded. Never commit plaintext secrets.
- **Image tags**: Use `latest` for upstream images (Cribl, OTEL, etc.). Do NOT pin specific versions — Renovate and upstream release tracking handle updates.
- **Worktrees**: Use `/init-worktree` before starting work. Work in feature branches.

## Deployment Verification (MANDATORY)

**Every change to k8s manifests MUST be verified by actually deploying to the cluster.** `make validate` alone is NOT sufficient.

After modifying any manifest, ConfigMap, or deployment script:

1. `make deploy-doppler` (or `kubectl apply -k k8s/overlays/local/` if SOPS key unavailable)
2. Wait for rollouts: `kubectl --context orbstack -n monitoring rollout status statefulset/<name>`
3. Verify pods are Running and Ready: `make status`
4. Check logs for errors: `kubectl --context orbstack -n monitoring logs statefulset/<name> --tail=20`
5. If health probes fail, check startup logs for the specific pod (not just `deploy/`)

Do NOT commit, push, or create PRs until all pods are Running and Ready.

## Architecture

See [Architecture Diagram](docs/ARCHITECTURE.md) for the full data flow and test coverage map.

Five StatefulSets in the monitoring namespace:

| StatefulSet | Role | UI |
|------------|------|-----|
| `otel-collector` | OTLP receiver, forwards to Cribl Stream Standalone | None |
| `cribl-edge-managed` | Cloud-managed edge, forwards to Cribl Cloud | None |
| `cribl-edge-standalone` | Local edge with pack, forwards to Cribl Stream Standalone | :30910 |
| `cribl-stream-standalone` | Local Stream leader with UI, outputs to Splunk HEC | :30900 |
| `cribl-mcp-server` | Cribl Cloud MCP API server for Claude Code | :30030 |

Directory layout:

- `k8s/base/` - Kustomize base manifests (portable, no real paths)
- `k8s/overlays/local/` - Generated overlay with real volume paths (gitignored)
- `scripts/` - Deployment and overlay generation scripts
- `docker/` - Dockerfiles for ephemeral AI containers
- `packs/` - Cribl Edge pack files (.crbl)
- `docs/` - Extended documentation

## CI

GitHub Actions run on every push and PR:

- **validate.yml** — Kustomize build + kubeconform schema validation + pre-commit hooks
- **validate-merged.yml** — Post-merge validation of current + last 2 commits on main

## Testing

```bash
make validate          # Validate kustomize builds + schemas
make validate-schemas  # Schema validation only
make deploy            # Full deploy to OrbStack
make status            # Check pod status
make test-smoke        # Run smoke tests (cluster connectivity)
make test-pipeline     # Run pipeline tests (OTLP flow)
make test-forwarding   # Run forwarding tests (Cribl routing)
```
