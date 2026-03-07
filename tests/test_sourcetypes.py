"""Tier 4: Per-sourcetype E2E tests for the Claude Code and Gemini log pipelines.

These tests verify that each sourcetype in the claude:code:* and gemini:cli:* families
is correctly assigned by the Cribl Stream pipeline when events travel through the full
path:
  Host FS → Cribl Edge Standalone → Cribl Stream Standalone → Splunk HEC

Five test classes:

  TestSourcetypeSentinels       — Write sentinel files to the host FS, wait for them
                                  to appear in Splunk with the correct sourcetype (6 sources).
  TestSourcetypeExistence       — Query Splunk for any existing data with the expected
                                  sourcetype (history, stats, plugins — live files we
                                  cannot safely write test data to).
  TestInputConfigurations       — Verify the Edge pod has the expected FileMonitor inputs
                                  active and that each expected datatype is configured.
  TestGeminiSourcetypeExistence — Query Splunk for gemini:cli:* and antigravity:* data.
  TestGeminiInputConfigurations — Verify the Edge pod has the expected Gemini datatypes.
"""

import errno
import json
import shutil
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from conftest import kubectl, kubectl_exec_no_fail
from helpers import query_splunk

# ---------------------------------------------------------------------------
# Sourcetype constants
# ---------------------------------------------------------------------------

SOURCETYPE_SESSION = "claude:code:session"
SOURCETYPE_SUBAGENT = "claude:code:subagent"
SOURCETYPE_HISTORY = "claude:code:history"
SOURCETYPE_STATS = "claude:code:stats"
SOURCETYPE_LOGS = "claude:code:logs"
SOURCETYPE_PLANS = "claude:code:plans"
SOURCETYPE_TASKS = "claude:code:tasks"
SOURCETYPE_TEAMS = "claude:code:teams"
SOURCETYPE_PLUGINS = "claude:code:plugins"
# claude:code:otel is covered by TestStreamToSplunkForwarding in test_forwarding.py

# Gemini sourcetype constants
SOURCETYPE_GEMINI_SESSION = "gemini:cli:session"
SOURCETYPE_GEMINI_LOGS = "gemini:cli:logs"
SOURCETYPE_GEMINI_SETTINGS = "gemini:cli:settings"
SOURCETYPE_GEMINI_PROJECTS = "gemini:cli:projects"
SOURCETYPE_ANTIGRAVITY_APP_LOGS = "antigravity:app-logs"
SOURCETYPE_ANTIGRAVITY_BRAIN = "antigravity:brain"
SOURCETYPE_ANTIGRAVITY_ANNOTATIONS = "antigravity:annotations"
SOURCETYPE_ANTIGRAVITY_CODE_TRACKER = "antigravity:code-tracker"

# ---------------------------------------------------------------------------
# Expected Edge FileMonitor input datatypes (datatype IDs in the pack)
# ---------------------------------------------------------------------------

EXPECTED_DATATYPES = [
    "claude-code-session",
    "claude-code-history",
    "claude-code-stats",
    "claude-code-logs",
    "claude-code-plans",
    "claude-code-tasks",
    "claude-code-teams",
    "claude-code-plugins",
]

EXPECTED_GEMINI_DATATYPES = [
    "gemini-cli-sessions",
    "gemini-cli-logs",
    "gemini-cli-settings",
    "gemini-cli-projects",
    "antigravity-app-logs",
    "antigravity-brain",
    "antigravity-annotations",
    "antigravity-code-tracker",
]

# ---------------------------------------------------------------------------
# Sentinel poll helper
# ---------------------------------------------------------------------------


def _wait_for_splunk(
    mgmt_url: str,
    admin_password: str,
    search: str,
    deadline_seconds: int = 90,
    poll_interval: int = 10,
) -> list[dict]:
    """Poll Splunk until results appear or the deadline is reached.

    Returns the result list (non-empty) on success, or an empty list if the
    deadline expires without finding any matching events.
    """
    deadline = time.time() + deadline_seconds
    while time.time() < deadline:
        results = query_splunk(mgmt_url, admin_password, search, earliest="-10m")
        if results:
            return results
        time.sleep(poll_interval)
    return []


# ---------------------------------------------------------------------------
# Sentinel file fixtures — one per sourcetype
# ---------------------------------------------------------------------------


@pytest.fixture
def sentinel_session():
    """Write a JSONL sentinel to ~/.claude/projects/-test-sourcetype/.

    Simulates a Claude Code session file routed to claude:code:session.
    Yields (path, sentinel_id). Cleans up after the test.
    """
    test_dir = Path.home() / ".claude" / "projects" / "-test-sourcetype"
    test_dir.mkdir(parents=True, exist_ok=True)
    sentinel_id = f"SRCTYPE_SESSION_{uuid.uuid4().hex[:12]}"
    sentinel_file = test_dir / f"test-{sentinel_id}.jsonl"
    sentinel_data = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sentinel": sentinel_id,
        "level": "info",
        "message": "sourcetype sentinel for claude:code:session",
    }
    sentinel_file.write_text(json.dumps(sentinel_data) + "\n")
    yield sentinel_file, sentinel_id
    try:
        sentinel_file.unlink()
    except FileNotFoundError:
        pass
    try:
        test_dir.rmdir()
    except OSError as exc:
        if exc.errno != errno.ENOTEMPTY:
            raise


@pytest.fixture
def sentinel_subagent():
    """Write a JSONL sentinel to ~/.claude/projects/-test-sourcetype/<uuid>/subagents/.

    The Cribl Stream pipeline differentiates subagent files from session files
    by the presence of 'subagents' in the source path, routing them to
    claude:code:subagent. Yields (path, sentinel_id). Cleans up after the test.
    """
    run_id = uuid.uuid4().hex[:12]
    subagent_dir = Path.home() / ".claude" / "projects" / "-test-sourcetype" / run_id / "subagents"
    subagent_dir.mkdir(parents=True, exist_ok=True)
    sentinel_id = f"SRCTYPE_SUBAGENT_{uuid.uuid4().hex[:12]}"
    sentinel_file = subagent_dir / f"test-{sentinel_id}.jsonl"
    sentinel_data = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sentinel": sentinel_id,
        "level": "info",
        "message": "sourcetype sentinel for claude:code:subagent",
    }
    sentinel_file.write_text(json.dumps(sentinel_data) + "\n")
    yield sentinel_file, sentinel_id
    try:
        sentinel_file.unlink()
    except FileNotFoundError:
        pass
    # Walk up and remove the run_id subdirectory tree if empty
    try:
        subagent_dir.rmdir()
    except OSError as exc:
        if exc.errno != errno.ENOTEMPTY:
            raise
    run_dir = subagent_dir.parent
    try:
        run_dir.rmdir()
    except OSError as exc:
        if exc.errno != errno.ENOTEMPTY:
            raise
    parent_dir = run_dir.parent
    try:
        parent_dir.rmdir()
    except OSError as exc:
        if exc.errno != errno.ENOTEMPTY:
            raise


@pytest.fixture
def sentinel_logs():
    """Write a JSONL sentinel to ~/.claude/logs/.

    Simulates a Claude Code log file routed to claude:code:logs.
    Yields (path, sentinel_id). Cleans up after the test.
    """
    logs_dir = Path.home() / ".claude" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    sentinel_id = f"SRCTYPE_LOGS_{uuid.uuid4().hex[:12]}"
    sentinel_file = logs_dir / f"test-{sentinel_id}.jsonl"
    sentinel_data = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sentinel": sentinel_id,
        "level": "info",
        "message": "sourcetype sentinel for claude:code:logs",
    }
    sentinel_file.write_text(json.dumps(sentinel_data) + "\n")
    yield sentinel_file, sentinel_id
    try:
        sentinel_file.unlink()
    except FileNotFoundError:
        pass


@pytest.fixture
def sentinel_plans():
    """Write a Markdown sentinel to ~/.claude/plans/.

    Simulates a Claude Code plans file routed to claude:code:plans.
    Yields (path, sentinel_id). Cleans up after the test.
    """
    plans_dir = Path.home() / ".claude" / "plans"
    plans_dir.mkdir(parents=True, exist_ok=True)
    sentinel_id = f"SRCTYPE_PLANS_{uuid.uuid4().hex[:12]}"
    sentinel_file = plans_dir / f"test-{sentinel_id}.md"
    sentinel_content = f"# Sentinel Plan\n\nsentinel: {sentinel_id}\n"
    sentinel_file.write_text(sentinel_content)
    yield sentinel_file, sentinel_id
    try:
        sentinel_file.unlink()
    except FileNotFoundError:
        pass


@pytest.fixture
def sentinel_tasks():
    """Write a JSON sentinel to ~/.claude/tasks/-test-sourcetype/.

    Simulates a Claude Code tasks file routed to claude:code:tasks.
    Yields (path, sentinel_id). Cleans up after the test.
    """
    tasks_dir = Path.home() / ".claude" / "tasks" / "-test-sourcetype"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    sentinel_id = f"SRCTYPE_TASKS_{uuid.uuid4().hex[:12]}"
    sentinel_file = tasks_dir / f"test-{sentinel_id}.json"
    sentinel_data = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sentinel": sentinel_id,
        "message": "sourcetype sentinel for claude:code:tasks",
    }
    sentinel_file.write_text(json.dumps(sentinel_data) + "\n")
    yield sentinel_file, sentinel_id
    try:
        sentinel_file.unlink()
    except FileNotFoundError:
        pass
    try:
        tasks_dir.rmdir()
    except OSError as exc:
        if exc.errno != errno.ENOTEMPTY:
            raise


@pytest.fixture
def sentinel_teams():
    """Write a JSON sentinel to ~/.claude/teams/-test-sourcetype/config.json.

    Simulates a Claude Code teams config file routed to claude:code:teams.
    The filename is fixed as config.json to match real team config structure.
    Yields (path, sentinel_id). Cleans up after the test.
    """
    teams_dir = Path.home() / ".claude" / "teams" / "-test-sourcetype"
    teams_dir.mkdir(parents=True, exist_ok=True)
    sentinel_id = f"SRCTYPE_TEAMS_{uuid.uuid4().hex[:12]}"
    sentinel_file = teams_dir / "config.json"
    sentinel_data = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sentinel": sentinel_id,
        "message": "sourcetype sentinel for claude:code:teams",
    }
    sentinel_file.write_text(json.dumps(sentinel_data) + "\n")
    yield sentinel_file, sentinel_id
    try:
        sentinel_file.unlink()
    except FileNotFoundError:
        pass
    try:
        teams_dir.rmdir()
    except OSError as exc:
        if exc.errno != errno.ENOTEMPTY:
            raise


# ---------------------------------------------------------------------------
# Sentinel-based E2E tests
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("cluster_ready")
class TestSourcetypeSentinels:
    """Verify each sourcetype is correctly assigned end-to-end: Host FS → Edge → Stream → Splunk.

    Each test writes a uniquely-identifiable sentinel file to the appropriate host
    directory, then polls Splunk until the sentinel appears with the expected
    sourcetype or the 90-second deadline expires.

    The FileMonitor input polls every 10–60 seconds depending on source; the
    90-second deadline accommodates up to one full poll cycle plus pipeline
    processing time.
    """

    def test_session_sourcetype(self, sentinel_session, splunk_client):
        """JSONL files in ~/.claude/projects/<proj>/ reach Splunk as claude:code:session.

        Writes a sentinel .jsonl into ~/.claude/projects/-test-sourcetype/ and verifies
        that it reaches Splunk index=claude with sourcetype=claude:code:session within 90s.
        """
        _, sentinel_id = sentinel_session
        mgmt_url, admin_password = splunk_client
        results = _wait_for_splunk(
            mgmt_url,
            admin_password,
            f'index=claude sourcetype={SOURCETYPE_SESSION} "{sentinel_id}"',
        )
        assert results, (
            f"Sentinel '{sentinel_id}' not found in Splunk with sourcetype={SOURCETYPE_SESSION} within 90s. "
            "Check that the Edge FileMonitor picks up ~/.claude/projects/ and that the "
            "Stream pipeline assigns sourcetype=claude:code:session for session files."
        )

    def test_subagent_sourcetype(self, sentinel_subagent, splunk_client):
        """JSONL files in ~/.claude/projects/<proj>/<run>/subagents/ reach Splunk as claude:code:subagent.

        The Cribl Stream pipeline differentiates subagent files from top-level session
        files by matching 'subagents' in the source path. Writes a sentinel into the
        subagents subdirectory and verifies the sourcetype assignment within 90s.
        """
        _, sentinel_id = sentinel_subagent
        mgmt_url, admin_password = splunk_client
        results = _wait_for_splunk(
            mgmt_url,
            admin_password,
            f'index=claude sourcetype={SOURCETYPE_SUBAGENT} "{sentinel_id}"',
        )
        assert results, (
            f"Sentinel '{sentinel_id}' not found in Splunk with sourcetype={SOURCETYPE_SUBAGENT} within 90s. "
            "Check that the Stream pipeline eval distinguishes subagent paths "
            "(containing 'subagents/') from top-level session files."
        )

    def test_logs_sourcetype(self, sentinel_logs, splunk_client):
        """JSONL files in ~/.claude/logs/ reach Splunk as claude:code:logs.

        Writes a sentinel .jsonl into ~/.claude/logs/ and verifies that it reaches
        Splunk index=claude with sourcetype=claude:code:logs within 90s.
        """
        _, sentinel_id = sentinel_logs
        mgmt_url, admin_password = splunk_client
        results = _wait_for_splunk(
            mgmt_url,
            admin_password,
            f'index=claude sourcetype={SOURCETYPE_LOGS} "{sentinel_id}"',
        )
        assert results, (
            f"Sentinel '{sentinel_id}' not found in Splunk with sourcetype={SOURCETYPE_LOGS} within 90s. "
            "Check that the Edge FileMonitor is configured to monitor ~/.claude/logs/ "
            "and that the Stream pipeline assigns sourcetype=claude:code:logs."
        )

    def test_plans_sourcetype(self, sentinel_plans, splunk_client):
        """Markdown files in ~/.claude/plans/ reach Splunk as claude:code:plans.

        Writes a sentinel .md file into ~/.claude/plans/ and verifies that it reaches
        Splunk index=claude with sourcetype=claude:code:plans within 90s.
        """
        _, sentinel_id = sentinel_plans
        mgmt_url, admin_password = splunk_client
        results = _wait_for_splunk(
            mgmt_url,
            admin_password,
            f'index=claude sourcetype={SOURCETYPE_PLANS} "{sentinel_id}"',
        )
        assert results, (
            f"Sentinel '{sentinel_id}' not found in Splunk with sourcetype={SOURCETYPE_PLANS} within 90s. "
            "Check that the Edge FileMonitor is configured to monitor ~/.claude/plans/ "
            "with a *.md file pattern and that the Stream pipeline assigns sourcetype=claude:code:plans."
        )

    def test_tasks_sourcetype(self, sentinel_tasks, splunk_client):
        """JSON files in ~/.claude/tasks/<proj>/ reach Splunk as claude:code:tasks.

        Writes a sentinel .json into ~/.claude/tasks/-test-sourcetype/ and verifies
        that it reaches Splunk index=claude with sourcetype=claude:code:tasks within 90s.
        """
        _, sentinel_id = sentinel_tasks
        mgmt_url, admin_password = splunk_client
        results = _wait_for_splunk(
            mgmt_url,
            admin_password,
            f'index=claude sourcetype={SOURCETYPE_TASKS} "{sentinel_id}"',
        )
        assert results, (
            f"Sentinel '{sentinel_id}' not found in Splunk with sourcetype={SOURCETYPE_TASKS} within 90s. "
            "Check that the Edge FileMonitor is configured to monitor ~/.claude/tasks/ "
            "and that the Stream pipeline assigns sourcetype=claude:code:tasks."
        )

    def test_teams_sourcetype(self, sentinel_teams, splunk_client):
        """JSON config.json files in ~/.claude/teams/<team>/ reach Splunk as claude:code:teams.

        Writes a sentinel config.json into ~/.claude/teams/-test-sourcetype/ and verifies
        that it reaches Splunk index=claude with sourcetype=claude:code:teams within 90s.
        """
        _, sentinel_id = sentinel_teams
        mgmt_url, admin_password = splunk_client
        results = _wait_for_splunk(
            mgmt_url,
            admin_password,
            f'index=claude sourcetype={SOURCETYPE_TEAMS} "{sentinel_id}"',
        )
        assert results, (
            f"Sentinel '{sentinel_id}' not found in Splunk with sourcetype={SOURCETYPE_TEAMS} within 90s. "
            "Check that the Edge FileMonitor is configured to monitor ~/.claude/teams/ "
            "and that the Stream pipeline assigns sourcetype=claude:code:teams."
        )


# ---------------------------------------------------------------------------
# Query-only existence tests (live files — no sentinel writes)
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("cluster_ready")
class TestSourcetypeExistence:
    """Verify that data with expected sourcetypes exists in Splunk (or skip informatively).

    These tests query Splunk for any events with the target sourcetype over the last
    24 hours. They do NOT write sentinel files because the source files are live system
    files (history.jsonl, stats-cache.json, installed plugins) that must not be
    overwritten or corrupted by test code.

    A missing result means either the pipeline is broken or the source file has not
    been updated recently. Tests skip (not fail) when no data is found so that a
    fresh environment does not produce false negatives before any Claude Code activity
    has occurred.
    """

    def test_history_sourcetype_exists(self, splunk_client):
        """Splunk should contain at least one event with sourcetype=claude:code:history in the last 24h.

        history.jsonl accumulates Claude Code conversation history. If the pipeline is
        working and Claude Code has been used, this sourcetype should have recent data.
        Skips (does not fail) when no data is found — this is expected on a fresh host.
        """
        mgmt_url, admin_password = splunk_client
        results = query_splunk(
            mgmt_url,
            admin_password,
            f"index=claude sourcetype={SOURCETYPE_HISTORY}",
            earliest="-24h",
        )
        if not results:
            pytest.skip(
                f"No events found in Splunk with sourcetype={SOURCETYPE_HISTORY} in the last 24h. "
                "This is expected if Claude Code has not been used recently or the pipeline "
                "has not yet ingested history.jsonl. Run Claude Code and re-test."
            )

    def test_stats_sourcetype_exists(self, splunk_client):
        """Splunk should contain at least one event with sourcetype=claude:code:stats in the last 24h.

        stats-cache.json is updated by Claude Code periodically. If the pipeline is
        working and Claude Code is installed, this sourcetype should have recent data.
        Skips (does not fail) when no data is found — this is expected on a fresh host.
        """
        mgmt_url, admin_password = splunk_client
        results = query_splunk(
            mgmt_url,
            admin_password,
            f"index=claude sourcetype={SOURCETYPE_STATS}",
            earliest="-24h",
        )
        if not results:
            pytest.skip(
                f"No events found in Splunk with sourcetype={SOURCETYPE_STATS} in the last 24h. "
                "This is expected if Claude Code stats have not been refreshed recently. "
                "Run Claude Code to populate stats-cache.json and re-test."
            )

    def test_plugins_sourcetype_exists(self, splunk_client):
        """Splunk should contain at least one event with sourcetype=claude:code:plugins in the last 24h.

        Installed Claude Code plugins are stored as JSON files under ~/.claude/plugins/.
        If the pipeline is working and plugins are installed, this sourcetype should
        have recent data. Skips (does not fail) when no data is found.
        """
        mgmt_url, admin_password = splunk_client
        results = query_splunk(
            mgmt_url,
            admin_password,
            f"index=claude sourcetype={SOURCETYPE_PLUGINS}",
            earliest="-24h",
        )
        if not results:
            pytest.skip(
                f"No events found in Splunk with sourcetype={SOURCETYPE_PLUGINS} in the last 24h. "
                "This is expected if no Claude Code plugins are installed or they have not "
                "been picked up by the FileMonitor since the last poll. Install a plugin and re-test."
            )


# ---------------------------------------------------------------------------
# Edge input configuration validation tests
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("cluster_ready")
class TestInputConfigurations:
    """Verify the Edge pod has the expected FileMonitor inputs active and configured.

    These tests inspect the running Edge pod to confirm that:
      1. The FileMonitor collector is actively finding files (log evidence).
      2. Each expected datatype appears in the loaded Edge pack configuration.

    They do not require Splunk connectivity and run against the live cluster only.
    """

    def test_file_monitor_inputs_active(self):
        """Edge pod logs should contain 'FileMonitor collector added' entries.

        This confirms that the FileMonitor input is active and has discovered at
        least one file on the host filesystem. Fetches full container logs (not
        limited by --since) to avoid false negatives when the pod has been running
        longer than the time window and no new files have appeared recently.
        """
        logs = kubectl("logs", "statefulset/cribl-edge-standalone")
        assert "FileMonitor collector added" in logs, (
            "Edge file monitor is not active — no 'FileMonitor collector added' entries found. "
            "The pack may not have been installed correctly, or CRIBL_VOLUME_DIR may be unset "
            "so that inputs.yml was written to the wrong directory."
        )

    def test_edge_inputs_yml_contains_claude_paths(self):
        """Edge inputs.yml should reference at least one ~/.claude/ monitoring path.

        Reads the injected inputs.yml from the edge pod's config directory and verifies
        that the Claude Code home directory path is present, confirming the pack's
        FileMonitor inputs were correctly written at startup.
        """
        output, returncode = kubectl_exec_no_fail(
            "statefulset/cribl-edge-standalone",
            "--",
            "sh",
            "-c",
            "cat ${CRIBL_VOLUME_DIR:-/opt/cribl}/local/edge/inputs.yml",
        )
        assert returncode == 0, (
            f"Could not read edge inputs.yml (exit {returncode}). "
            "Check that CRIBL_BEFORE_START_CMD wrote inputs.yml to local/edge/."
        )
        assert "/home/claude/.claude/" in output or "$CLAUDE_HOME/.claude/" in output, (
            f"Expected '/home/claude/.claude/' or '$CLAUDE_HOME/.claude/' path in edge inputs.yml, got:\n{output[:500]}"
        )

    @pytest.mark.parametrize("datatype", EXPECTED_DATATYPES)
    def test_edge_input_datatype_configured(self, datatype: str):
        """Each expected datatype should appear in the Edge's loaded pack configuration.

        Reads the pack inputs configuration from within the edge pod and verifies that
        the datatype ID is present. A missing datatype means the pack was not installed
        correctly or the datatype was removed from the pack.

        Args:
            datatype: The Cribl datatype ID to search for, e.g. 'claude-code-session'.
        """
        # The pack config is written to the pack's local inputs directory.
        # We search in inputs.yml because that is where CRIBL_BEFORE_START_CMD
        # writes the merged configuration for the edge runtime to load.
        output, returncode = kubectl_exec_no_fail(
            "statefulset/cribl-edge-standalone",
            "--",
            "sh",
            "-c",
            "cat ${CRIBL_VOLUME_DIR:-/opt/cribl}/local/edge/inputs.yml",
        )
        if returncode != 0:
            pytest.skip(f"Could not read edge inputs.yml (exit {returncode}); skipping datatype presence check.")
        assert datatype in output, (
            f"Datatype '{datatype}' not found in edge inputs.yml. "
            "The pack may be missing this input or the datatype ID may have changed. "
            f"inputs.yml excerpt (first 500 chars):\n{output[:500]}"
        )


# ---------------------------------------------------------------------------
# Gemini sentinel fixtures (safe write paths only)
# ---------------------------------------------------------------------------


@pytest.fixture
def sentinel_antigravity_brain():
    """Write a Markdown sentinel to ~/.gemini/antigravity/brain/ matching the antigravity-brain input.

    The Gemini pack's antigravity-brain input monitors $GEMINI_HOME/.gemini/antigravity/brain/
    for *.md files. Yields (path, sentinel_id). Cleans up after the test.
    """
    brain_dir = Path.home() / ".gemini" / "antigravity" / "brain"
    brain_dir.mkdir(parents=True, exist_ok=True)
    sentinel_id = f"SRCTYPE_ANTIGRAVITY_BRAIN_{uuid.uuid4().hex[:12]}"
    sentinel_file = brain_dir / f"sentinel-{sentinel_id}.md"
    sentinel_file.write_text(f"# Sentinel\n\nsentinel: {sentinel_id}\n")
    yield sentinel_file, sentinel_id
    try:
        sentinel_file.unlink()
    except FileNotFoundError:
        pass


# ---------------------------------------------------------------------------
# Gemini sentinel-based E2E tests
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("cluster_ready")
class TestGeminiSourcetypeSentinels:
    """Verify Gemini sourcetypes are correctly assigned end-to-end: Host FS → Edge → Stream → Splunk.

    Uses safe write paths only (tmp/, antigravity/brain/) to avoid corrupting live Gemini data.
    """

    def test_gemini_session_sourcetype(self, splunk_client):
        """Real Gemini CLI session reaches Splunk as gemini:cli:session.

        Invokes the Gemini CLI with a unique sentinel prompt, then polls Splunk until
        the session file content appears with sourcetype=gemini:cli:session within 120s.
        This proves the full pipeline: Gemini CLI → ~/.gemini/tmp/ → Edge FileMonitor
        (gemini-cli-sessions input) → Cribl Stream → Splunk HEC.
        """
        gemini_bin = shutil.which("gemini") or ""
        if not gemini_bin:
            pytest.skip("gemini CLI not found in PATH; cannot run E2E session test")

        sentinel_id = f"GEMINI_E2E_{uuid.uuid4().hex[:12]}"

        # gemini -p launches an agentic session that can run for several minutes.
        # We only need it to start and write session files to ~/.gemini/tmp/; we
        # don't need it to finish. Catch TimeoutExpired and continue so Splunk
        # polling can still verify the session data made it through the pipeline.
        try:
            result = subprocess.run(
                [gemini_bin, "-p", f"kubernetes-monitoring test sentinel {sentinel_id}"],
                capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode != 0:
                pytest.skip(f"gemini CLI exited {result.returncode}: {result.stderr[:200]}")
        except subprocess.TimeoutExpired:
            pass  # session files already written; proceed to poll Splunk

        mgmt_url, admin_password = splunk_client
        results = _wait_for_splunk(
            mgmt_url,
            admin_password,
            f'index=gemini sourcetype={SOURCETYPE_GEMINI_SESSION} "{sentinel_id}"',
            deadline_seconds=120,
        )
        assert results, (
            f"Gemini session sentinel '{sentinel_id}' not found in Splunk with "
            f"sourcetype={SOURCETYPE_GEMINI_SESSION} within 120s. "
            "Check that the Edge FileMonitor picks up ~/.gemini/tmp/**/*.json "
            "(gemini-cli-sessions input) and that the Stream pipeline assigns "
            "sourcetype=gemini:cli:session."
        )

    def test_antigravity_brain_sourcetype(self, sentinel_antigravity_brain, splunk_client):
        """*.md files in ~/.gemini/antigravity/brain/ reach Splunk as antigravity:brain.

        Writes a sentinel *.md into ~/.gemini/antigravity/brain/ and verifies that it reaches
        Splunk index=gemini with sourcetype=antigravity:brain within 90s.
        """
        _, sentinel_id = sentinel_antigravity_brain
        mgmt_url, admin_password = splunk_client
        results = _wait_for_splunk(
            mgmt_url,
            admin_password,
            f'index=gemini sourcetype={SOURCETYPE_ANTIGRAVITY_BRAIN} "{sentinel_id}"',
        )
        assert results, (
            f"Sentinel '{sentinel_id}' not found in Splunk with sourcetype={SOURCETYPE_ANTIGRAVITY_BRAIN} within 90s. "
            "Check that the Edge FileMonitor picks up ~/.gemini/antigravity/brain/*.md and that the "
            "Stream pipeline assigns sourcetype=antigravity:brain for Antigravity brain files."
        )


# ---------------------------------------------------------------------------
# Gemini query-only existence tests (live files — no sentinel writes)
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("cluster_ready")
class TestGeminiSourcetypeExistence:
    """Verify that Gemini data exists in Splunk (or skip informatively).

    Queries Splunk for any events with gemini:cli:* and antigravity:* sourcetypes
    over the last 24 hours. Skips (not fails) when no data is found — expected on
    a fresh host before any Gemini CLI activity.
    """

    def test_gemini_cli_sourcetypes_exist(self, splunk_client):
        """Splunk should contain at least one event with sourcetype=gemini:cli:* in the last 24h."""
        mgmt_url, admin_password = splunk_client
        results = query_splunk(
            mgmt_url,
            admin_password,
            "index=gemini sourcetype=gemini:cli:*",
            earliest="-24h",
        )
        if not results:
            pytest.skip(
                "No events found in Splunk with sourcetype=gemini:cli:* in the last 24h. "
                "This is expected if Gemini CLI has not been used recently or the pipeline "
                "has not yet ingested Gemini files. Use Gemini CLI and re-test."
            )

    def test_antigravity_sourcetypes_exist(self, splunk_client):
        """Splunk should contain at least one event with sourcetype=antigravity:* in the last 24h."""
        mgmt_url, admin_password = splunk_client
        results = query_splunk(
            mgmt_url,
            admin_password,
            "index=gemini sourcetype=antigravity:*",
            earliest="-24h",
        )
        if not results:
            pytest.skip(
                "No events found in Splunk with sourcetype=antigravity:* in the last 24h. "
                "This is expected if Antigravity IDE has not been used recently or the pipeline "
                "has not yet ingested Antigravity files."
            )


# ---------------------------------------------------------------------------
# Gemini Edge input configuration validation tests
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("cluster_ready")
class TestGeminiInputConfigurations:
    """Verify the Edge pod has the expected Gemini FileMonitor inputs active and configured.

    Inspects the merged inputs.yml in the running Edge pod to confirm that CMD_3
    (Gemini pack merge) ran successfully and that all Gemini datatypes are present.
    """

    def test_edge_inputs_yml_contains_gemini_paths(self):
        """Edge inputs.yml should reference ~/.gemini monitoring paths.

        Reads the merged inputs.yml from the edge pod and verifies that the Gemini
        home directory path is present, confirming CMD_3 (Gemini pack merge) ran.
        """
        output, returncode = kubectl_exec_no_fail(
            "statefulset/cribl-edge-standalone",
            "--",
            "sh",
            "-c",
            "cat ${CRIBL_VOLUME_DIR:-/opt/cribl}/local/edge/inputs.yml",
        )
        assert returncode == 0, (
            f"Could not read edge inputs.yml (exit {returncode}). "
            "Check that CRIBL_BEFORE_START_CMD_3 merged the Gemini pack inputs."
        )
        assert "/home/gemini/.gemini" in output or "$GEMINI_HOME/.gemini" in output, (
            f"Expected Gemini home path in edge inputs.yml, got:\n{output[:500]}\n"
            "CRIBL_BEFORE_START_CMD_3 may have failed — check pod startup logs."
        )

    @pytest.mark.parametrize("datatype", EXPECTED_GEMINI_DATATYPES)
    def test_edge_gemini_datatype_configured(self, datatype: str):
        """Each expected Gemini datatype should appear in the Edge's merged inputs.yml.

        Confirms CMD_3 merged the Gemini pack inputs into the Claude pack inputs.yml
        successfully. A missing datatype indicates the merge step failed.

        Args:
            datatype: The Cribl datatype ID to search for, e.g. 'gemini-cli-sessions'.
        """
        output, returncode = kubectl_exec_no_fail(
            "statefulset/cribl-edge-standalone",
            "--",
            "sh",
            "-c",
            "cat ${CRIBL_VOLUME_DIR:-/opt/cribl}/local/edge/inputs.yml",
        )
        if returncode != 0:
            pytest.skip(f"Could not read edge inputs.yml (exit {returncode}); skipping Gemini datatype check.")
        assert datatype in output, (
            f"Gemini datatype '{datatype}' not found in edge inputs.yml. "
            "CRIBL_BEFORE_START_CMD_3 (Gemini pack merge) may have failed. "
            f"inputs.yml excerpt (first 500 chars):\n{output[:500]}"
        )
