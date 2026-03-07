"""Tier 0: Unit tests for conftest.py utility functions — no cluster required.

These tests cover the kubectl helper utilities in conftest.py that contain
non-trivial logic: secret decoding, multi-key lookups, exec error handling,
port-forward retry logic, and JSON output parsing.
All subprocess/kubectl calls are mocked so no cluster is needed.
"""

import base64
import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest
import requests
from conftest import (
    kubectl,
    kubectl_exec_no_fail,
    kubectl_json,
    kubectl_secret,
    kubectl_secret_values,
    port_forward_get,
)


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


class TestKubectl:
    def test_returns_stripped_stdout_on_success(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "NAME  READY\n"
        mock_result.stderr = ""
        with patch("conftest.subprocess.run", return_value=mock_result):
            output = kubectl("get", "pods")
        assert output == "NAME  READY"

    def test_raises_runtime_error_on_nonzero_returncode(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error from server: not found"
        with patch("conftest.subprocess.run", return_value=mock_result):
            with pytest.raises(RuntimeError, match="failed"):
                kubectl("get", "pods")

    def test_error_message_includes_stderr(self):
        mock_result = MagicMock()
        mock_result.returncode = 2
        mock_result.stdout = ""
        mock_result.stderr = "connection refused"
        with patch("conftest.subprocess.run", return_value=mock_result):
            with pytest.raises(RuntimeError, match="connection refused"):
                kubectl("cluster-info")


class TestKubectlJson:
    def test_parses_json_output(self):
        payload = {"items": [{"name": "pod-1"}]}
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(payload) + "\n"
        mock_result.stderr = ""
        with patch("conftest.subprocess.run", return_value=mock_result):
            result = kubectl_json("get", "pods")
        assert result == payload

    def test_propagates_kubectl_error(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "secret not found"
        with patch("conftest.subprocess.run", return_value=mock_result):
            with pytest.raises(RuntimeError):
                kubectl_json("get", "secret", "missing")

    def test_raises_json_decode_error_on_invalid_output(self):
        """kubectl_json passes stdout through json.loads; invalid JSON must raise JSONDecodeError."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "not valid json\n"
        mock_result.stderr = ""
        with patch("conftest.subprocess.run", return_value=mock_result):
            with pytest.raises(json.JSONDecodeError):
                kubectl_json("get", "pods")


class TestPortForwardGet:
    def _make_proc(self, poll_return=None):
        proc = MagicMock()
        proc.poll.return_value = poll_return
        return proc

    def test_returns_response_on_successful_connection(self):
        proc = self._make_proc(poll_return=None)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        with patch("conftest.subprocess.Popen", return_value=proc):
            with patch("conftest.requests.get", return_value=mock_resp):
                with patch("conftest.time.time", side_effect=[0, 1]):
                    resp = port_forward_get("otel-collector", 13133, 13133, "/")
        assert resp is mock_resp
        proc.terminate.assert_called_once()
        proc.wait.assert_called_once()

    def test_fails_when_process_exits_early(self):
        proc = self._make_proc(poll_return=1)
        with patch("conftest.subprocess.Popen", return_value=proc):
            with patch("conftest.time.time", side_effect=[0, 1]):
                with pytest.raises(pytest.fail.Exception, match="exited before request"):
                    port_forward_get("otel-collector", 13133, 13133, "/")

    def test_times_out_when_connection_always_refused(self):
        proc = self._make_proc(poll_return=None)
        with patch("conftest.subprocess.Popen", return_value=proc):
            with patch("conftest.requests.get", side_effect=requests.exceptions.ConnectionError("refused")):
                with patch("conftest.time.time", side_effect=[0, 0, 16]):
                    with patch("conftest.time.sleep"):
                        with pytest.raises(pytest.fail.Exception, match="Timed out"):
                            port_forward_get("otel-collector", 13133, 13133, "/", timeout_seconds=15)
        proc.terminate.assert_called_once()
        proc.wait.assert_called_once()

    def test_cleans_up_process_when_process_exits_early(self):
        """terminate() and wait() must be called in the finally block even when process exits early."""
        proc = self._make_proc(poll_return=1)
        with patch("conftest.subprocess.Popen", return_value=proc):
            with patch("conftest.time.time", side_effect=[0, 1]):
                with pytest.raises(pytest.fail.Exception, match="exited before request"):
                    port_forward_get("otel-collector", 13133, 13133, "/")
        proc.terminate.assert_called_once()
        proc.wait.assert_called_once()
