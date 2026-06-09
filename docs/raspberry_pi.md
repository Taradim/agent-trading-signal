# Raspberry Pi Operation

This project is light enough to run from a Raspberry Pi with `uv`, Git, and a
weekly scheduler.

The recommended production setup is a user-level `systemd` timer. It is more
observable than cron, keeps logs in `journalctl`, and can catch up after a reboot
thanks to `Persistent=true`.

## Setup

```bash
sudo apt update
sudo apt install -y git curl
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Clone the repository:

```bash
git clone https://github.com/Taradim/agent-trading-signal.git ~/agent-trading-signal
cd ~/agent-trading-signal
uv sync
```

If the repository already exists:

```bash
cd ~/agent-trading-signal
git pull --ff-only
uv sync
```

## SSH Access

Prefer a reserved DHCP address in the router and a stable SSH alias over relying
on `.local` name resolution.

Example `~/.ssh/config` entry:

```sshconfig
Host raspi5
  HostName 192.168.1.72
  User taradim
  HostKeyAlias raspi5.local
```

Then connect with:

```bash
ssh raspi5
```

If `raspi5.local` stops resolving but the IP still works, the issue is usually
local mDNS/Bonjour resolution rather than the Pi SSH service.

## Manual Run

```bash
cd ~/agent-trading-signal
uv run trading-signal weekly-report
```

The weekly report uses the recommended core ETF + BTC configuration, downloads
fresh prices, writes `data/market/recommended_prices.csv`, and creates
`reports/weekly_decision.md`. It also appends a machine-readable run record to
`reports/history/weekly_signals.csv`.

Update `config/current_portfolio.toml` after each manual rebalance so the next
run can show whether a trade is still needed:

```toml
[allocation]
SMH = 1.0
```

For deeper research or exports, run the lower-level commands directly:

```bash
uv run trading-signal download-prices --out data/market/prices.csv
uv run trading-signal signal --prices data/market/prices.csv --out reports/latest-signal.md
uv run trading-signal backtest \
  --prices data/market/prices.csv \
  --out reports/backtest.md \
  --equity-out reports/equity_curve.csv \
  --trades-out reports/trades.csv
```

## systemd Timer

Install the user-level timer:

```bash
cd ~/agent-trading-signal
./scripts/install_pi_systemd_timer.sh
```

Check the timer:

```bash
systemctl --user list-timers agent-trading-signal-weekly.timer
systemctl --user status agent-trading-signal-weekly.timer
```

Run the job immediately:

```bash
systemctl --user start agent-trading-signal-weekly.service
```

Read logs:

```bash
journalctl --user -u agent-trading-signal-weekly.service -n 100 --no-pager
```

The service runs:

```bash
~/agent-trading-signal/scripts/run_weekly_report.sh
```

That script pulls the latest Git changes with `git pull --ff-only`, runs
`uv sync`, then generates the weekly report.

## Cron Fallback

Open the crontab:

```bash
crontab -e
```

Run every Monday at 09:00 Paris time:

```cron
0 9 * * 1 cd /home/pi/agent-trading-signal && uv run trading-signal weekly-report
```

## Operational Notes

- Keep generated `data/` and `reports/` folders out of Git.
- Pull updates manually before the weekly run if the strategy code changed.
- Add notification later once the report format is stable.
