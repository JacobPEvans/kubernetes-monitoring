"""Pure utility functions extracted from test logic for unit testing."""

import json
import re


def parse_otel_error_lines(log_text: str) -> list[str]:
    """Return operational error lines from OTEL collector logs.

    OTEL collector log format: TIMESTAMP\\tLEVEL\\tFILE\\tMESSAGE\\tJSON
    Lines with \\terror\\t are error-level operational entries.
    Info-level retry lines (e.g. "Exporting failed. Will retry...") are
    expected transient noise and are excluded.
    """
    return [line for line in log_text.splitlines() if "\terror\t" in line]


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


def url_present_in_outputs_yaml(url: str, yaml_text: str) -> bool:
    """Return True if url appears as a 'url:' value in the YAML text.

    Matches lines of the form:  url: <value>  (with optional surrounding whitespace).
    """
    return bool(re.search(rf"^\s*url:\s*{re.escape(url)}\s*$", yaml_text, re.MULTILINE))
