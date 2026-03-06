"""Tier 0: Unit tests for conftest.py utility functions — no cluster required.

These tests cover the kubectl helper utilities in conftest.py that contain
non-trivial logic: secret decoding, multi-key lookups, and exec error handling.
All subprocess/kubectl calls are mocked so no cluster is needed.
"""

import base64
import subprocess
from unittest.mock import MagicMock, patch

import pytest
from conftest import kubectl_exec_no_fail, kubectl_secret, kubectl_secret_values


def _encode(value: str) -> str:
    """Base64-encode a string as Kubernetes stores secret values."""
    return base64.b64encode(value.encode()).decode()


def _secret_response(items: dict[str, str]) -> dict:
    """Build a kubectl_json response for a Secret with the given key→value pairs."""
    return {"data": {k: _encode(v) for k, v in items.items()}}


class TestKubectlSecret:
    def test_returns_decoded_value(self):
        data = _secret_response({"password": "secret123"})
        with patch("conftest.kubectl_json", return_value=data):
            result = kubectl_secret("my-secret", "password")
        assert result == "secret123"

    def test_raises_on_missing_key(self):
        data = _secret_response({"other-key": "value"})
        with patch("conftest.kubectl_json", return_value=data):
            with pytest.raises(RuntimeError, match="not found or empty"):
                kubectl_secret("my-secret", "missing-key")

    def test_raises_on_empty_data_section(self):
        with patch("conftest.kubectl_json", return_value={"data": {}}):
            with pytest.raises(RuntimeError, match="not found or empty"):
                kubectl_secret("my-secret", "any-key")

    def test_decodes_non_ascii_values(self):
        raw = "pässwörд"  # cspell:disable-line
        encoded = base64.b64encode(raw.encode()).decode()
        data = {"data": {"key": encoded}}
        with patch("conftest.kubectl_json", return_value=data):
            result = kubectl_secret("my-secret", "key")
        assert result == raw


class TestKubectlSecretValues:
    def test_returns_all_decoded_values(self):
        data = _secret_response({"token": "abc123", "url": "https://splunk:8089"})
        with patch("conftest.kubectl_json", return_value=data):
            result = kubectl_secret_values("my-secret", ["token", "url"])
        assert result == {"token": "abc123", "url": "https://splunk:8089"}

    def test_single_key(self):
        data = _secret_response({"api-key": "mykey"})
        with patch("conftest.kubectl_json", return_value=data):
            result = kubectl_secret_values("my-secret", ["api-key"])
        assert result == {"api-key": "mykey"}

    def test_raises_on_missing_key(self):
        data = _secret_response({"token": "abc123"})
        with patch("conftest.kubectl_json", return_value=data):
            with pytest.raises(RuntimeError, match="not found or empty"):
                kubectl_secret_values("my-secret", ["token", "missing"])

    def test_raises_when_first_key_missing(self):
        data = _secret_response({"present": "value"})
        with patch("conftest.kubectl_json", return_value=data):
            with pytest.raises(RuntimeError, match="not found or empty"):
                kubectl_secret_values("my-secret", ["absent", "present"])

    def test_returns_empty_dict_for_empty_keys_list(self):
        data = _secret_response({"key": "value"})
        with patch("conftest.kubectl_json", return_value=data):
            result = kubectl_secret_values("my-secret", [])
        assert result == {}


class TestKubectlExecNoFail:
    def test_returns_stdout_and_zero_on_success(self):
        mock_result = MagicMock()
        mock_result.stdout = "command output\n"
        mock_result.returncode = 0
        with patch("conftest.subprocess.run", return_value=mock_result):
            stdout, code = kubectl_exec_no_fail("mypod", "--", "ls")
        assert stdout == "command output"
        assert code == 0

    def test_strips_trailing_whitespace_from_stdout(self):
        mock_result = MagicMock()
        mock_result.stdout = "  trimmed  \n"
        mock_result.returncode = 0
        with patch("conftest.subprocess.run", return_value=mock_result):
            stdout, code = kubectl_exec_no_fail("mypod", "--", "echo")
        assert stdout == "trimmed"

    def test_returns_empty_string_and_one_on_timeout(self):
        with patch("conftest.subprocess.run", side_effect=subprocess.TimeoutExpired("kubectl", 30)):
            stdout, code = kubectl_exec_no_fail("mypod", "--", "slow-cmd")
        assert stdout == ""
        assert code == 1

    def test_returns_nonzero_returncode_on_failure(self):
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.returncode = 127
        with patch("conftest.subprocess.run", return_value=mock_result):
            stdout, code = kubectl_exec_no_fail("mypod", "--", "bad-command")
        assert code == 127

    def test_passes_args_to_kubectl_exec(self):
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.returncode = 0
        with patch("conftest.subprocess.run", return_value=mock_result) as mock_run:
            kubectl_exec_no_fail("statefulset/otel-collector", "-c", "collector", "--", "wget", "-qO-", "/")
        called_cmd = mock_run.call_args[0][0]
        assert "exec" in called_cmd
        assert "statefulset/otel-collector" in called_cmd
        assert "wget" in called_cmd
