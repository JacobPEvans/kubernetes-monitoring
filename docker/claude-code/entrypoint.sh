#!/bin/sh
set -e

# Validate required environment
if [ -z "${CLAUDE_API_KEY:-}" ]; then
  echo "ERROR: CLAUDE_API_KEY environment variable is required"
  exit 1
fi

# Configure logging
export CLAUDE_LOG_DIR="/logs"
export CLAUDE_LOG_LEVEL="${CLAUDE_LOG_LEVEL:-info}"

echo "Starting Claude Code container"
echo "  Workspace: /workspace"
echo "  Log dir: /logs"
echo "  Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Run claude with provided arguments
exec claude "$@"
