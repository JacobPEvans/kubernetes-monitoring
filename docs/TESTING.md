# Testing Guide

## Overview

Tests are organized into four tiers, each building on the previous:

| Tier | Command | What It Verifies |
|------|---------|--------------------|
| 1 — Smoke | `make test-smoke` | Cluster reachable, all 5 pods Running, health endpoints respond |
| 2 — Pipeline | `make test-pipeline` | OTLP gRPC/HTTP send completes without error (A1) |
| 3 — Forwarding | `make test-forwarding` | Data flows through each pipeline leg, including Splunk receipt |
| 4 — Unit | `make test-unit` | Pure logic unit tests (no cluster required) |

Run all tiers: `make test-all` (or individually with the commands above).

## Prerequisites

- OrbStack running with the monitoring namespace deployed: `make deploy-doppler`
- Test venv installed: `make test-setup`
- Splunk HEC token configured: `SPLUNK_HEC_TOKEN` must be set in Doppler `iac-conf-mgmt/prd`
- Splunk management credentials in secret: `splunk-hec-config` must have `mgmt-url` and `admin-password` keys (populated automatically by `make deploy-doppler` when `SPLUNK_PASSWORD` is set)

## Test Files

### `tests/test_smoke.py`

Verifies infrastructure health — all pods running, all StatefulSets ready, service endpoints respond.
Does not verify data flow, only that components are alive.

### `tests/test_pipeline.py`

Verifies OTLP data can be ingested (A1: Client → OTEL Collector).
Sends a trace via gRPC and HTTP, asserts no transport errors.

### `tests/test_forwarding.py`

The main integration test suite. Three test classes:

**`TestCollectorToStreamForwarding`** — OTEL Collector → Cribl Stream (A4)

- Verifies no OTEL exporter errors after sending a trace
- Verifies Stream's OTLP input metrics show received events

**`TestStreamToSplunkForwarding`** — Cribl Stream → Splunk HEC (A7)

- `test_splunk_hec_output_healthy`: Cribl's output health API shows Green
- `test_splunk_hec_health_endpoint`: Splunk HEC health URL returns 200
- `test_splunk_hec_token_accepted`: POST to Splunk HEC with real token returns 200
- `test_splunk_hec_url_matches_secret`: Runtime config matches the Kubernetes secret
- `test_cribl_stream_no_output_errors`: Stream logs show no non-retryable output errors
- `test_cribl_stream_events_flowing`: Stream shows `outBytes > 0` in stats logs
- `test_otlp_events_reach_splunk_realtime` ✓Splunk: Sends OTLP trace with unique ID, **queries Splunk** for `index=claude` within 60s

**`TestClaudeCodeLogPipeline`** — Host FS → Edge → Stream → Splunk (A2+A5+A7)

- `test_claude_home_mount_accessible`: Edge pod can read `~/.claude/projects/`
- `test_sentinel_file_visible_in_edge_pod`: Host file appears in pod immediately
- `test_edge_file_monitor_config_path`: Pack input config has correct monitoring path
- `test_edge_file_monitor_picks_up_sentinel`: Edge FileMonitor logs "collector added" within 35s
- `test_edge_output_not_devnull`: Edge's default output routes to stream-hec (not devnull)
- `test_edge_file_input_active`: Edge FileMonitor is actively collecting files
- `test_file_events_reach_splunk_realtime` ✓Splunk: Writes sentinel `.jsonl`, **queries Splunk** for `index=claude sourcetype=claude:code:session` within 90s

Tests marked ✓Splunk verify data arrived in Splunk — not just that it was sent.

### `tests/test_unit.py`

Pure logic tests (no cluster needed):

- `test_parse_otel_error_lines`: Validates OTEL log parser
- `test_find_flowing_stats`: Validates Cribl stats parser
- `test_url_present_in_outputs_yaml`: Validates YAML URL matcher

### `tests/helpers.py`

Shared utility functions:

- `parse_otel_error_lines(log_text)`: Filters OTEL collector logs for error-level operational entries
- `find_flowing_stats(log_text)`: Finds Cribl Stream logs where `outBytes > 0`
- `url_present_in_outputs_yaml(url, yaml_text)`: Checks Splunk URL in Cribl output YAML
- `query_splunk(mgmt_url, admin_password, search, earliest)`: Queries Splunk REST API, returns list of result dicts

### `tests/conftest.py`

Shared fixtures:

- `cluster_ready`: Session fixture, skips all tests if OrbStack unreachable
- `splunk_client`: Returns `(mgmt_url, admin_password)` from `splunk-hec-config` secret; skips if keys absent

## Running Specific Tests

```bash
# Run a single test
make test-setup
.venv/bin/pytest tests/test_forwarding.py::TestClaudeCodeLogPipeline::test_file_events_reach_splunk_realtime -v

# Run all forwarding tests
make test-forwarding

# Run with extra verbosity for debugging
.venv/bin/pytest tests/test_forwarding.py -v -s
```

## Troubleshooting

### `splunk_client` fixture skipped

The `splunk-hec-config` secret is missing `mgmt-url` or `admin-password` keys. Run:

```bash
make deploy-doppler
```

Requires `SPLUNK_PASSWORD` and `SPLUNK_NETWORK` set in Doppler `iac-conf-mgmt/prd`.

### `test_file_events_reach_splunk_realtime` fails (sentinel not in Splunk)

Check each pipeline leg:

1. **Edge mount**: `kubectl exec -n monitoring cribl-edge-standalone-0 -- ls /home/claude/.claude/projects/`
2. **Edge FileMonitor**: `kubectl logs -n monitoring cribl-edge-standalone-0 --since=5m | grep FileMonitor`
3. **Edge→Stream sent**: Check Edge outputs API `sentCount` for `stream-hec`
4. **Stream→Splunk errors**: `kubectl logs -n monitoring cribl-stream-standalone-0 --since=5m | grep "400\|error"`
5. **Splunk HEC config**: `kubectl exec -n monitoring cribl-stream-standalone-0 -- cat /opt/cribl/data/local/cribl/outputs.yml`

### Tests pass but data goes to wrong Splunk index

The `force-splunk-meta` pipeline must set `index` (no underscore) — NOT `_index`. If events appear with `sourcetype=httpevent` or `index=default`, the pipeline is not running or has wrong field names. Check:

```bash
kubectl exec -n monitoring cribl-stream-standalone-0 -- \
  cat /opt/cribl/data/local/cribl/pipelines/force-splunk-meta/conf.yml
```

## Known Limitations

- **A3 (Host FS → Edge Managed)**: Not verified by forwarding tests; only pod health is checked
- **A6 (Edge Managed → Cribl Cloud)**: Not locally testable (cloud-managed)
- **A9 (MCP Server → Cribl Cloud)**: Not locally testable

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full test coverage map.
