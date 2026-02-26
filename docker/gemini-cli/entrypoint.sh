#!/bin/sh
set -e

# Validate required environment
if [ -z "${GEMINI_API_KEY:-}" ]; then
  echo "ERROR: GEMINI_API_KEY environment variable is required"
  exit 1
fi

# Configure logging
export LOG_DIR="/logs"

echo "Starting Gemini CLI container"
echo "  Workspace: /workspace"
echo "  Log dir: /logs"
echo "  Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Run gemini with provided arguments
exec gemini "$@"
