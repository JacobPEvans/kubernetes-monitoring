"""Tier 0: Pure unit tests — no cluster required.

These tests cover utility functions in helpers.py and can run in CI
without any Kubernetes infrastructure.
"""

import json

from helpers import find_flowing_stats, parse_otel_error_lines, url_present_in_outputs_yaml


class TestParseOtelErrorLines:
    def test_returns_error_lines(self):
        log = "2024-01-01T00:00:00Z\terror\texporter/exporter.go:99\texport failed\t{}\n"
        assert parse_otel_error_lines(log) == [log.strip()]

    def test_ignores_info_lines(self):
        log = "2024-01-01T00:00:00Z\tinfo\texporter/retry.go:50\tExporting failed. Will retry...\t{}\n"
        assert parse_otel_error_lines(log) == []

    def test_empty_log(self):
        assert parse_otel_error_lines("") == []

    def test_mixed_levels(self):
        lines = [
            "2024-01-01T00:00:00Z\tinfo\tfile.go:1\tok\t{}",
            "2024-01-01T00:00:01Z\terror\tfile.go:2\tbad\t{}",
            "2024-01-01T00:00:02Z\twarn\tfile.go:3\tmeh\t{}",
        ]
        result = parse_otel_error_lines("\n".join(lines))
        assert result == [lines[1]]


class TestFindFlowingStats:
    def _make_stat_line(self, message="_raw stats", out_events=1, out_bytes=100, **kwargs):
        data = {"message": message, "outEvents": out_events, "outBytes": out_bytes, **kwargs}
        return json.dumps(data)

    def test_finds_flowing_line(self):
        line = self._make_stat_line()
        result = find_flowing_stats(line)
        assert result == [line]

    def test_excludes_zero_out_bytes(self):
        line = self._make_stat_line(out_bytes=0)
        assert find_flowing_stats(line) == []

    def test_excludes_zero_out_events(self):
        line = self._make_stat_line(out_events=0)
        assert find_flowing_stats(line) == []

    def test_excludes_wrong_message(self):
        line = self._make_stat_line(message="other stats")
        assert find_flowing_stats(line) == []

    def test_ignores_non_json_lines(self):
        log = "plain text line\n" + self._make_stat_line()
        result = find_flowing_stats(log)
        assert len(result) == 1

    def test_empty_log(self):
        assert find_flowing_stats("") == []


class TestUrlPresentInOutputsYaml:
    def test_finds_exact_url(self):
        url = "https://192.168.0.200:8088/services/collector"
        yaml = f"outputs:\n  url: {url}\n"
        assert url_present_in_outputs_yaml(url, yaml) is True

    def test_finds_url_with_leading_spaces(self):
        url = "https://192.168.0.200:8088/services/collector"
        yaml = f"    url: {url}\n"
        assert url_present_in_outputs_yaml(url, yaml) is True

    def test_rejects_partial_match(self):
        url = "https://192.168.0.200:8088/services/collector"
        yaml = f"url: {url}/extra\n"
        assert url_present_in_outputs_yaml(url, yaml) is False

    def test_rejects_missing_url(self):
        yaml = "host: splunk.example.com\nport: 8088\n"
        assert url_present_in_outputs_yaml("https://splunk.example.com:8088/services/collector", yaml) is False

    def test_special_chars_in_url_are_escaped(self):
        url = "https://192.168.0.200:8088/services/collector"
        # Dots in IP would match any char without re.escape — ensure they don't
        yaml = "url: https://192X168Y0Z200:8088/services/collector\n"
        assert url_present_in_outputs_yaml(url, yaml) is False
