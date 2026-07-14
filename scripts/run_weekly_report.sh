#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="${AGENT_TRADING_SIGNAL_REPO_DIR:-$HOME/agent-trading-signal}"
PORTFOLIO_PATH="${AGENT_TRADING_SIGNAL_PORTFOLIO_PATH:-config/current_portfolio.local.toml}"
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

cd "$REPO_DIR"

send_telegram_text() {
  local text="$1"

  case "${AGENT_TRADING_SIGNAL_NOTIFY:-0}" in
    1|true|TRUE|yes|YES) ;;
    *) return 0 ;;
  esac

  if [[ -z "${AGENT_TRADING_SIGNAL_TELEGRAM_BOT_TOKEN:-}" || -z "${AGENT_TRADING_SIGNAL_TELEGRAM_CHAT_ID:-}" ]]; then
    echo "Telegram notification requested, but Telegram credentials are missing" >&2
    return 0
  fi

  curl --fail --silent --show-error \
    --max-time 15 \
    --data-urlencode "chat_id=${AGENT_TRADING_SIGNAL_TELEGRAM_CHAT_ID}" \
    --data-urlencode "text=${text}" \
    --data-urlencode "disable_web_page_preview=true" \
    "https://api.telegram.org/bot${AGENT_TRADING_SIGNAL_TELEGRAM_BOT_TOKEN}/sendMessage" \
    >/dev/null || true
}

on_error() {
  local status=$?
  local command=${BASH_COMMAND:-unknown}
  send_telegram_text "Trading Signal FAILED on $(hostname) at $(date '+%Y-%m-%d %H:%M:%S %Z')
Exit: ${status}
Step: ${command}
Check: ~/agent-trading-signal/logs/weekly_report.log"
  exit "$status"
}

retry_command() {
  local attempts="$1"
  local delay_seconds="$2"
  shift 2

  local attempt=1
  while true; do
    if "$@"; then
      return 0
    fi

    if (( attempt >= attempts )); then
      return 1
    fi

    echo "Command failed; retrying in ${delay_seconds}s (${attempt}/${attempts}): $*" >&2
    sleep "$delay_seconds"
    attempt=$((attempt + 1))
  done
}

trap on_error ERR

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
  if ! retry_command 5 30 git pull --ff-only; then
    echo "WARNING: git pull failed after retries; continuing with the current local checkout." >&2
    send_telegram_text "Trading Signal warning on $(hostname): GitHub pull failed after retries at $(date '+%Y-%m-%d %H:%M:%S %Z'). Continuing with local code."
  fi
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

retry_command 3 30 uv sync
uv run trading-signal weekly-report --portfolio "$PORTFOLIO_PATH" "${NOTIFY_ARGS[@]}"
