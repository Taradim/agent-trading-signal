#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${AGENT_TRADING_SIGNAL_ENV_FILE:-$HOME/.config/agent-trading-signal/env}"
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

send_telegram_text() {
  local text="$1"

  if [[ -z "${AGENT_TRADING_SIGNAL_TELEGRAM_BOT_TOKEN:-}" || -z "${AGENT_TRADING_SIGNAL_TELEGRAM_CHAT_ID:-}" ]]; then
    echo "Telegram credentials are missing; cannot send healthcheck" >&2
    exit 1
  fi

  curl --fail --silent --show-error \
    --max-time 15 \
    --data-urlencode "chat_id=${AGENT_TRADING_SIGNAL_TELEGRAM_CHAT_ID}" \
    --data-urlencode "text=${text}" \
    --data-urlencode "disable_web_page_preview=true" \
    "https://api.telegram.org/bot${AGENT_TRADING_SIGNAL_TELEGRAM_BOT_TOKEN}/sendMessage" \
    >/dev/null
}

timestamp="$(date '+%Y-%m-%d %H:%M:%S %Z')"
uptime_value="$(uptime -p 2>/dev/null || uptime)"
weekly_state="$(systemctl --user is-active agent-trading-signal-weekly.timer 2>/dev/null || true)"

message="raspi5 OK · ${uptime_value} · weekly ${weekly_state:-unknown}"

send_telegram_text "$message"
echo "Sent Pi healthcheck at ${timestamp}"
