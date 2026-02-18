# kubernetes-monitoring

Kubernetes monitoring manifests for local OrbStack cluster.

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
2. Wait for rollouts: `kubectl --context orbstack -n monitoring rollout status deployment/<name>`
3. Verify pods are Running and Ready: `make status`
4. Check logs for errors: `kubectl --context orbstack -n monitoring logs deploy/<name> --tail=20`
5. If health probes fail, check startup logs for the specific pod (not just `deploy/`)

Do NOT commit, push, or create PRs until all pods are Running and Ready.

## Architecture

Five deployments in the monitoring namespace:

| Deployment | Role | UI |
|------------|------|-----|
| `otel-collector` | OTLP receiver, forwards to managed edge | None |
| `cribl-edge-managed` | Cloud-managed edge, receives OTLP on :9420 | None |
| `cribl-edge-standalone` | Local edge with pack, Splunk HEC output | :30910 |
| `cribl-stream-standalone` | Local Stream leader with UI | :30900 |
| `cribl-stream-managed` | Cloud-managed Stream worker | None |

Directory layout:

- `k8s/base/` - Kustomize base manifests (portable, no real paths)
- `k8s/overlays/local/` - Generated overlay with real volume paths (gitignored)
- `scripts/` - Deployment and overlay generation scripts
- `docker/` - Dockerfiles for ephemeral AI containers
- `packs/` - Cribl Edge pack files (.crbl)
- `docs/` - Extended documentation

## Testing

```bash
make validate     # Validate kustomize builds cleanly
make deploy       # Full deploy to OrbStack
make status       # Check pod status
```
