#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"

mkdir -p "$SYSTEMD_USER_DIR"

install -m 0644 \
  "$REPO_DIR/deploy/systemd/agent-trading-signal-weekly.service" \
  "$SYSTEMD_USER_DIR/agent-trading-signal-weekly.service"
install -m 0644 \
  "$REPO_DIR/deploy/systemd/agent-trading-signal-weekly.timer" \
  "$SYSTEMD_USER_DIR/agent-trading-signal-weekly.timer"
chmod +x "$REPO_DIR/scripts/run_weekly_report.sh"

systemctl --user daemon-reload
systemctl --user enable --now agent-trading-signal-weekly.timer

echo "Installed agent-trading-signal-weekly.timer"
systemctl --user list-timers agent-trading-signal-weekly.timer
