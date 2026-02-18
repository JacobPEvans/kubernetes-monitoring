# kubernetes-monitoring

Kubernetes monitoring manifests for local OrbStack cluster.

## Key Rules

- **PLACEHOLDER_HOME_DIR**: Base manifests use literal `PLACEHOLDER_HOME_DIR` for hostPath volumes. NEVER replace with real paths in `k8s/base/`.
- **Overlays are gitignored**: `k8s/overlays/local/` is generated at deploy time by `scripts/generate-overlay.sh` and must not be committed.
- **Deploy workflow**: `make deploy` generates overlay + creates secrets + applies kustomize.
- **Secrets**: All secrets in SOPS (`secrets.enc.yaml`). Doppler project/config stored in SOPS, never hardcoded. Never commit plaintext secrets.
- **Image tags**: Pin to specific versions, not `:latest`.
- **Worktrees**: Use `/init-worktree` before starting work. Work in feature branches.

## Architecture

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
