# AI Containers

Ephemeral containers for running Claude Code and Gemini CLI as Kubernetes jobs.

## Building Images

```bash
make build-images
```

This builds:

- `kubernetes-monitoring/claude-code:latest` - Claude Code CLI in Alpine
- `kubernetes-monitoring/gemini-cli:latest` - Gemini CLI in Alpine

## Running Jobs

### Claude Code

```bash
make run-claude
```

Or with custom arguments:

```bash
kubectl -n monitoring create job claude-task-$(date +%s) \
  --from=job/claude-code-job \
  -- "Analyze the code in /workspace and suggest improvements"
```

### Gemini CLI

```bash
make run-gemini
```

## Log Collection

Job logs are written to `/logs/` inside the container, which maps to `~/logs/ai-jobs/` on the host. Both OTEL Collector and Cribl Edge monitor this directory for new log files.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `CLAUDE_API_KEY` | Yes (Claude) | Anthropic API key |
| `GEMINI_API_KEY` | Yes (Gemini) | Google AI API key |
| `CLAUDE_LOG_LEVEL` | No | Log level (default: info) |

## Cleanup

Jobs auto-delete after 1 hour (`ttlSecondsAfterFinished: 3600`). To manually clean up:

```bash
kubectl -n monitoring delete jobs -l job-type=ai-ephemeral
```
