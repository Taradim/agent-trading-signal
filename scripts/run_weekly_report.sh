#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${AGENT_TRADING_SIGNAL_REPO_DIR:-$HOME/agent-trading-signal}"
PORTFOLIO_PATH="${AGENT_TRADING_SIGNAL_PORTFOLIO_PATH:-config/current_portfolio.local.toml}"
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

cd "$REPO_DIR"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is not installed or not available in PATH" >&2
  echo "Install it with: curl -LsSf https://astral.sh/uv/install.sh | sh" >&2
  exit 127
fi

if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  if ! git diff --quiet --ignore-submodules --; then
    echo "Tracked local changes detected; refusing to pull over them." >&2
    echo "Commit, stash, or reset local tracked changes before the weekly run." >&2
    exit 2
  fi
  git pull --ff-only
fi

if [[ ! -f "$PORTFOLIO_PATH" ]]; then
  cp config/current_portfolio.toml "$PORTFOLIO_PATH"
  chmod 600 "$PORTFOLIO_PATH"
  echo "Created local portfolio file at $PORTFOLIO_PATH"
  echo "Update it after manual trades so future reports compare against live allocation."
fi

NOTIFY_ARGS=()
case "${AGENT_TRADING_SIGNAL_NOTIFY:-0}" in
  1|true|TRUE|yes|YES)
    NOTIFY_ARGS+=(--notify)
    ;;
esac

uv sync
uv run trading-signal weekly-report --portfolio "$PORTFOLIO_PATH" "${NOTIFY_ARGS[@]}"
