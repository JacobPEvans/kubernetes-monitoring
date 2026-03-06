"""Tier 0: Static manifest structure tests — no cluster required.

These tests enforce the architecture invariants documented in CLAUDE.md
by reading manifest files as text, without any cluster or external dependencies.

  - Edge → Stream → Splunk is the ONLY allowed data path
  - Base manifests must use PLACEHOLDER_HOME_DIR for hostPath user-space volumes
"""

import re
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).parent.parent / "k8s" / "base"
NETWORK_POLICIES_DIR = BASE_DIR / "network-policies"
EDGE_STANDALONE_DIR = BASE_DIR / "cribl-edge-standalone"

# Absolute paths under these prefixes are valid system mounts in base manifests.
_SYSTEM_PATH_PREFIXES = ("/var/", "/proc/", "/sys/", "/dev/", "/etc/", "/tmp/", "/run/")


def _base_yaml_files_with_hostpath() -> list[Path]:
    """Return sorted list of base YAML files that contain a hostPath volume entry."""
    return sorted(f for f in BASE_DIR.rglob("*.yaml") if "kustomization" not in f.name and "hostPath" in f.read_text())


class TestArchitectureInvariant:
    """Verify Edge → Stream → Splunk is the only allowed data path (CLAUDE.md invariant)."""

    def test_edge_standalone_output_targets_stream_not_splunk(self):
        """Edge standalone ConfigMap outputs.yml must route to cribl-stream-standalone, not Splunk directly."""
        configmap = EDGE_STANDALONE_DIR / "configmap-cribl-config.yaml"
        text = configmap.read_text()

        assert "cribl-stream-standalone" in text, (
            "Edge standalone outputs.yml must target cribl-stream-standalone, not Splunk directly"
        )

        # Every url: line in the configmap must point to the stream pod, not an external host
        url_lines = [line.strip() for line in text.splitlines() if re.match(r"^\s*url:", line)]
        assert url_lines, "Edge standalone configmap must contain at least one url: directive"
        for line in url_lines:
            assert "cribl-stream-standalone" in line, (
                f"Edge standalone output URL must target cribl-stream-standalone, got: {line}"
            )

    def test_edge_standalone_network_policy_references_stream_pod_selector(self):
        """allow-edge-standalone-egress must have a podSelector entry for cribl-stream-standalone."""
        policy_text = (NETWORK_POLICIES_DIR / "allow-edge-standalone-egress.yaml").read_text()
        assert "cribl-stream-standalone" in policy_text, (
            "Edge standalone egress policy must restrict to cribl-stream-standalone via podSelector"
        )

    def test_edge_standalone_network_policy_uses_hec_port(self):
        """Edge standalone egress to stream must specify port 8088 (Cribl HEC)."""
        policy_text = (NETWORK_POLICIES_DIR / "allow-edge-standalone-egress.yaml").read_text()
        assert "8088" in policy_text, (
            "Edge standalone egress policy must specify port 8088 for HEC forwarding to Stream"
        )

    def test_stream_egress_policy_allows_external_splunk(self):
        """Stream egress must reach external Splunk — policy must NOT restrict by podSelector."""
        policy_text = (NETWORK_POLICIES_DIR / "allow-stream-egress.yaml").read_text()
        # A podSelector in the egress rule would block external Splunk access
        assert "podSelector" not in policy_text, (
            "Stream egress policy must not use podSelector — it must reach external Splunk hosts"
        )

    def test_stream_egress_policy_uses_splunk_hec_port(self):
        """Stream egress must specify port 8088 for Splunk HEC forwarding."""
        policy_text = (NETWORK_POLICIES_DIR / "allow-stream-egress.yaml").read_text()
        assert "8088" in policy_text, "Stream egress policy must specify port 8088 for Splunk HEC forwarding"

    def test_default_deny_covers_both_ingress_and_egress(self):
        """Default deny policy must block both ingress and egress in the monitoring namespace."""
        policy_text = (NETWORK_POLICIES_DIR / "default-deny.yaml").read_text()
        assert "Ingress" in policy_text, "Default deny policy must include Ingress in policyTypes"
        assert "Egress" in policy_text, "Default deny policy must include Egress in policyTypes"
        assert "podSelector: {}" in policy_text, "Default deny policy must apply to all pods (empty podSelector)"


class TestPlaceholderHomeDirRule:
    """Verify base manifests use PLACEHOLDER_HOME_DIR for user-space hostPath volumes.

    CLAUDE.md rule: 'Base manifests use literal PLACEHOLDER_HOME_DIR for hostPath
    volumes. NEVER replace with real paths in k8s/base/.'
    """

    @pytest.mark.parametrize(
        "yaml_file",
        _base_yaml_files_with_hostpath(),
        ids=lambda f: f.relative_to(BASE_DIR).as_posix(),
    )
    def test_base_manifest_has_no_real_user_paths(self, yaml_file: Path):
        """hostPath user-space paths in base manifests must use PLACEHOLDER_HOME_DIR, not real paths."""
        text = yaml_file.read_text()
        # Extract all path: values from the manifest
        path_values = re.findall(r"path:\s*(\S+)", text)
        for path in path_values:
            if not path.startswith("/"):
                # PLACEHOLDER_HOME_DIR/... or other non-absolute paths are OK
                continue
            if path == "/" or path.startswith(_SYSTEM_PATH_PREFIXES):
                # Root mount or system directories are OK
                continue
            # Any other absolute path is a real user-space path — forbidden in k8s/base/
            pytest.fail(
                f"{yaml_file.relative_to(BASE_DIR)}: hostPath '{path}' is a real user-space path — "
                "use PLACEHOLDER_HOME_DIR instead (see CLAUDE.md)"
            )
