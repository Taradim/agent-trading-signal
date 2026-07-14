#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
WEEKLY_SERVICE_DROPIN_DIR="$SYSTEMD_USER_DIR/agent-trading-signal-weekly.service.d"
CONFIG_DIR="$HOME/.config/agent-trading-signal"
ENV_FILE="$CONFIG_DIR/env"

mkdir -p "$SYSTEMD_USER_DIR"
mkdir -p "$WEEKLY_SERVICE_DROPIN_DIR"
mkdir -p "$CONFIG_DIR"
mkdir -p "$REPO_DIR/logs"

if command -v loginctl >/dev/null 2>&1; then
  loginctl enable-linger "$USER"
fi

if [[ ! -f "$ENV_FILE" ]]; then
  cat >"$ENV_FILE" <<'EOF'
# Optional notification settings for the weekly Raspberry Pi run.
# Keep this file private; it can contain Telegram secrets.
AGENT_TRADING_SIGNAL_NOTIFY=0
# AGENT_TRADING_SIGNAL_TELEGRAM_BOT_TOKEN=
# AGENT_TRADING_SIGNAL_TELEGRAM_CHAT_ID=
EOF
  chmod 600 "$ENV_FILE"
fi

if git -C "$REPO_DIR" remote get-url origin >/dev/null 2>&1; then
  git -C "$REPO_DIR" remote set-url --push origin DISABLED_BY_PI_LEAST_PRIVILEGE
fi

install -m 0644 \
  "$REPO_DIR/deploy/systemd/agent-trading-signal-weekly.service" \
  "$SYSTEMD_USER_DIR/agent-trading-signal-weekly.service"
install -m 0644 \
  "$REPO_DIR/deploy/systemd/agent-trading-signal-weekly.timer" \
  "$SYSTEMD_USER_DIR/agent-trading-signal-weekly.timer"
install -m 0644 \
  "$REPO_DIR/deploy/systemd/agent-trading-signal-weekly-logging.conf" \
  "$WEEKLY_SERVICE_DROPIN_DIR/logging.conf"
install -m 0644 \
  "$REPO_DIR/deploy/systemd/agent-trading-signal-healthcheck.service" \
  "$SYSTEMD_USER_DIR/agent-trading-signal-healthcheck.service"
install -m 0644 \
  "$REPO_DIR/deploy/systemd/agent-trading-signal-healthcheck.timer" \
  "$SYSTEMD_USER_DIR/agent-trading-signal-healthcheck.timer"
chmod +x "$REPO_DIR/scripts/run_weekly_report.sh"
chmod +x "$REPO_DIR/scripts/send_pi_healthcheck.sh"

systemctl --user daemon-reload
systemctl --user enable --now agent-trading-signal-weekly.timer
systemctl --user enable --now agent-trading-signal-healthcheck.timer

echo "Installed agent-trading-signal-weekly.timer"
echo "Installed agent-trading-signal-healthcheck.timer"
echo "Notification environment file: $ENV_FILE"
echo "Disabled git push URL for origin in this Pi clone"
echo "Enabled systemd linger for $USER so the timer can run without an SSH session"
systemctl --user list-timers agent-trading-signal-weekly.timer
systemctl --user list-timers agent-trading-signal-healthcheck.timer
