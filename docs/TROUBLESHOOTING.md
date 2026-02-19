# Troubleshooting

## Pods Not Starting

### ImagePullBackOff

```bash
kubectl -n monitoring describe pod <pod-name>
```

Check that OrbStack has internet access and the image tag exists.

### CrashLoopBackOff

```bash
kubectl -n monitoring logs <pod-name> --previous
```

Common causes:

- Missing secrets (cribl-cloud-config, cribl-stream-admin)
- Invalid Cribl Cloud URL format
- Port conflicts with other services

### Pending

```bash
kubectl -n monitoring describe pod <pod-name>
```

Check for resource constraints or node affinity issues.

## Volumes Not Mounting

OrbStack automatically mounts macOS home directories. Verify:

```bash
# Check if the host path exists
ls -la ~/.claude/logs/
ls -la ~/Library/Logs/Ollama/
ls -la ~/logs/

# Check volume mounts in pod
kubectl -n monitoring exec statefulset/cribl-edge-managed -- ls -la /var/log/claude/
```

If directories don't exist on the host, create them:

```bash
mkdir -p ~/.claude/logs ~/logs ~/logs/ai-jobs
```

## Secrets Missing

```bash
# List secrets
kubectl -n monitoring get secrets

# Re-create secrets
sops exec-env secrets.enc.yaml './scripts/deploy.sh'
```

## OTEL Not Receiving Data

```bash
# Check OTEL health
kubectl -n monitoring exec statefulset/otel-collector -- curl -s http://localhost:13133/

# Check OTEL logs for errors
kubectl -n monitoring logs statefulset/otel-collector

# Test OTLP endpoint from host
curl -X POST http://localhost:30318/v1/traces \
  -H "Content-Type: application/json" \
  -d '{"resourceSpans":[]}'
```

## Cribl Edge Pack Not Loaded

```bash
# Check init container logs
kubectl -n monitoring logs statefulset/cribl-edge-managed -c install-cribl-pack

# Verify pack file exists
ls -la packs/cc-edge-claude-code.crbl

# Check pack was copied
kubectl -n monitoring exec statefulset/cribl-edge-managed -- ls -la /opt/cribl/data/packs/
```

## Port Conflicts

If NodePort services fail to bind:

```bash
# Check what's using the ports
lsof -i :30317 -i :30318 -i :30900 -i :30910
```

## Reset Everything

```bash
make clean
sops exec-env secrets.enc.yaml 'make deploy'
```
