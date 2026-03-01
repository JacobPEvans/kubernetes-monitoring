"""Pure utility functions extracted from test logic for unit testing."""

import base64
import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request


def parse_otel_error_lines(log_text: str) -> list[str]:
    """Return operational error lines from OTEL collector logs.

    OTEL collector log format: TIMESTAMP\\tLEVEL\\tFILE\\tMESSAGE\\tJSON
    Lines with \\terror\\t are error-level operational entries.
    Info-level retry lines (e.g. "Exporting failed. Will retry...") are
    expected transient noise and are excluded.

    "Failed to open file" errors from fileconsumer are also excluded — they
    occur when the OTEL collector tracks pod log paths that get cleaned up
    after short-lived pods (CronJobs) complete. This is expected OS-level
    noise and does not indicate a pipeline failure.
    """
    return [line for line in log_text.splitlines() if "\terror\t" in line and "Failed to open file" not in line]


def find_flowing_stats(log_text: str) -> list[str]:
    """Return log lines where Cribl Stream _raw stats show outBytes > 0.

    Checks outBytes > 0 (bytes physically sent to an external output),
    not just outEvents (which counts pipeline-internal routing).
    """
    results = []
    for line in log_text.splitlines():
        try:
            data = json.loads(line)
            if data.get("message") == "_raw stats" and data.get("outEvents", 0) > 0 and data.get("outBytes", 0) > 0:
                results.append(line)
        except (ValueError, KeyError):
            continue
    return results


def query_splunk(
    mgmt_url: str,
    admin_password: str,
    search: str,
    earliest: str = "-15m",
    verify_tls: bool = False,
    timeout_seconds: int = 30,
) -> list[dict]:
    """Query Splunk via the REST search/export API and return result dicts.

    Uses urllib (no third-party deps). By default, TLS verification is
    disabled for the self-signed cert on the LAN Splunk instance; callers
    can set verify_tls=True to enforce certificate validation.

    Returns an empty list on transient connectivity or auth errors so that
    polling loops can continue retrying until their deadline.

    Args:
        mgmt_url: Splunk management URL, e.g. "https://192.168.0.200:8089"
        admin_password: Splunk admin password
        search: SPL search string (without leading "search" keyword)
        earliest: Splunk earliest time modifier, e.g. "-15m"
        verify_tls: If True, enforce TLS certificate and hostname checks.
        timeout_seconds: Per-request socket timeout in seconds.

    Returns:
        List of result dicts from Splunk's export API, or [] on error.
    """
    ctx = ssl.create_default_context()
    if not verify_tls:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    body = urllib.parse.urlencode(
        {
            "search": f"search {search}",
            "earliest_time": earliest,
            "output_mode": "json",
        }
    ).encode()

    credentials = f"admin:{admin_password}"
    encoded = base64.b64encode(credentials.encode()).decode()
    req = urllib.request.Request(
        f"{mgmt_url}/services/search/jobs/export",
        data=body,
        headers={"Authorization": f"Basic {encoded}"},
        method="POST",
    )

    results = []
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=timeout_seconds) as resp:
            for line in resp:
                line = line.decode().strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if "result" in data:
                        results.append(data["result"])
                except (ValueError, KeyError):
                    continue
    except (urllib.error.URLError, OSError):
        return []
    return results


def url_present_in_outputs_yaml(url: str, yaml_text: str) -> bool:
    """Return True if url appears as a 'url:' value in the YAML text.

    Matches lines of the form:  url: <value>  (with optional surrounding whitespace).
    """
    return bool(re.search(rf"^\s*url:\s*{re.escape(url)}\s*$", yaml_text, re.MULTILINE))
