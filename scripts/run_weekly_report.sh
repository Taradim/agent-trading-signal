#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${AGENT_TRADING_SIGNAL_REPO_DIR:-$HOME/agent-trading-signal}"
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

cd "$REPO_DIR"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is not installed or not available in PATH" >&2
  echo "Install it with: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
  exit 127
fi

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git pull --ff-only
fi

uv sync
uv run trading-signal weekly-report
