# Architecture: Data Flow and Test Coverage

## Data Flow Diagram

```mermaid
flowchart LR
    Client[External Client]
    HostFS[Host Filesystem]
    OtelCollector["otel-collector\nNodePort :30317/:30318"]
    EdgeStandalone["cribl-edge-standalone\nUI :30910"]
    EdgeManaged[cribl-edge-managed]
    StreamStandalone["cribl-stream-standalone\nUI :30900"]
    SplunkHEC["Splunk HEC\n:8088 HEC"]
    CriblCloud["Cribl Cloud\n(external)"]
    McpServer["cribl-mcp-server\nNodePort :30030"]
    ClaudeCode["Claude Code\n(macOS)"]
    HCio["healthchecks.io\n(external)"]

    Client -->|"A1: OTLP gRPC/HTTP"| OtelCollector
    HostFS -->|"A2: file input"| EdgeStandalone
    HostFS -->|"A3: file input"| EdgeManaged
    OtelCollector -->|"A4: gRPC :4317"| StreamStandalone
    EdgeStandalone -->|"A5: HEC :8088"| StreamStandalone
    EdgeManaged -->|"A6: cloud-managed"| CriblCloud
    StreamStandalone -->|"A7: HEC HTTPS"| SplunkHEC
    ClaudeCode -->|"A8: MCP HTTP :30030"| McpServer
    McpServer -->|"A9: API HTTPS :443"| CriblCloud
    StreamStandalone -->|"H1: health :9000"| HCio
    SplunkHEC -->|"H2: health :8088"| HCio
    EdgeStandalone -->|"H3: health :9420"| HCio
    OtelCollector -->|"H4: health :13133"| HCio
```

## Test Coverage Map

| Arrow | Path | Test(s) | File |
|-------|------|---------|------|
| A1 | Client → OTEL Collector | `test_send_trace_grpc`, `test_send_trace_http` | test_pipeline.py |
| A2 | Host FS → Edge Standalone | `test_claude_home_mount_accessible`,<br>`test_sentinel_file_visible_in_edge_pod`,<br>`test_edge_file_monitor_config_path`,<br>`test_edge_file_monitor_picks_up_sentinel`,<br>`test_edge_output_not_devnull`,<br>`test_edge_file_input_active` | test_forwarding.py |
| A3 | Host FS → Edge Managed | (file mount, verified by pod health) | test_smoke.py |
| A4 | OTEL Collector → Cribl Stream | `test_no_export_errors_after_send`, `test_cribl_stream_received_otlp_data` | test_forwarding.py |
| A5 | Edge Standalone → Cribl Stream (HEC :8088) | `test_edge_output_not_devnull`, `test_edge_file_input_active`, `test_file_events_reach_splunk_realtime` | test_forwarding.py |
| A6 | Edge Managed → Cribl Cloud | Not locally testable (cloud-managed) | — |
| A7 | Cribl Stream → Splunk HEC | `test_splunk_hec_output_healthy`,<br>`test_splunk_hec_health_endpoint`,<br>`test_splunk_hec_token_accepted`,<br>`test_splunk_hec_url_matches_secret`,<br>`test_cribl_stream_no_output_errors`,<br>`test_cribl_stream_events_flowing`,<br>`test_otlp_events_reach_splunk_realtime` ✓Splunk | test_forwarding.py |
| A2+A5+A7 | Full .claude/projects pipeline (E2E) | `test_file_events_reach_splunk_realtime` ✓Splunk | test_forwarding.py |
| A8 | Claude Code → MCP Server | `test_mcp_initialize_returns_200`, `test_mcp_response_content_type`, `test_mcp_initialize_protocol_version` | test_smoke.py |
| A9 | MCP Server → Cribl Cloud | Not locally testable (cloud-managed) | — |
| H1 | pipeline-heartbeat → Stream health → healthchecks.io | `test_network_policy_exists[allow-heartbeat-egress]` | test_smoke.py |
| H2 | heartbeat-splunk → Splunk HEC health → healthchecks.io | `test_network_policy_exists[allow-heartbeat-splunk-egress]` | test_smoke.py |
| H3 | heartbeat-edge → Edge health → healthchecks.io | `test_network_policy_exists[allow-heartbeat-edge-egress]` | test_smoke.py |
| H4 | heartbeat-otel → OTEL health → healthchecks.io | `test_network_policy_exists[allow-heartbeat-otel-egress]` | test_smoke.py |
