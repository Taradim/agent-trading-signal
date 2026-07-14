#!/usr/bin/env bash
set -euo pipefail

PI_HOST="${AGENT_TRADING_SIGNAL_PI_HOST:-192.168.1.72}"
PI_NAME="${AGENT_TRADING_SIGNAL_PI_NAME:-raspi5}"
ENV_FILE="${AGENT_TRADING_SIGNAL_ENV_FILE:-$HOME/.config/agent-trading-signal/env}"
LOG_FILE="${AGENT_TRADING_SIGNAL_PI_WATCHDOG_LOG:-$HOME/.config/agent-trading-signal/pi_watchdog.log}"

mkdir -p "$(dirname "$LOG_FILE")"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

timestamp="$(date '+%Y-%m-%d %H:%M:%S %Z')"

send_telegram_text() {
  local text="$1"

  if [[ -z "${AGENT_TRADING_SIGNAL_TELEGRAM_BOT_TOKEN:-}" || -z "${AGENT_TRADING_SIGNAL_TELEGRAM_CHAT_ID:-}" ]]; then
    echo "${timestamp} missing Telegram credentials" >>"$LOG_FILE"
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

if ping -c 2 -W 1000 "$PI_HOST" >/dev/null 2>&1; then
  echo "${timestamp} ${PI_NAME} OK at ${PI_HOST}" >>"$LOG_FILE"
  exit 0
fi

message="Pi watchdog ALERT
${PI_NAME} is not reachable at ${PI_HOST}
Time: ${timestamp}
From: $(hostname)
Action: check power/network, then ssh ${PI_NAME}"

echo "${timestamp} ${PI_NAME} DOWN at ${PI_HOST}" >>"$LOG_FILE"
send_telegram_text "$message"
