#!/bin/bash
set -e

if [ ! -f .runner ]; then
  ./config.sh \
    --url "https://github.com/${GITHUB_REPOSITORY}" \
    --token "${RUNNER_TOKEN}" \
    --labels "${RUNNER_LABELS:-self-hosted,Linux}" \
    --name "${RUNNER_NAME:-orbstack-runner}" \
    --unattended \
    --replace
fi

# Clear the registration token from the environment after config completes.
# The token is single-use and expires in 1h, but no reason to leave it visible
# via /proc/*/environ or docker inspect longer than necessary.
unset RUNNER_TOKEN

cleanup() {
  # Registration token was already consumed and unset. Deregistration requires
  # a fresh removal token — generate one if gh CLI is available, otherwise
  # warn the operator.
  local remove_token
  if command -v gh >/dev/null 2>&1 && [ -n "${GITHUB_REPOSITORY:-}" ]; then
    remove_token=$(gh api "repos/${GITHUB_REPOSITORY}/actions/runners/remove-token" --method POST --jq '.token' 2>/dev/null || true)
  fi
  if [ -n "${remove_token:-}" ]; then
    ./config.sh remove --token "$remove_token" 2>/dev/null || true
  else
    echo "Warning: Could not obtain a removal token; runner may need manual removal via GitHub UI."
  fi
}
trap cleanup EXIT

./run.sh
