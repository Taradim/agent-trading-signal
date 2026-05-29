# Raspberry Pi Operation

This project is light enough to run from a Raspberry Pi with `uv`, Git, and a
weekly scheduler.

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

## Manual Run

```bash
cd ~/agent-trading-signal
uv run trading-signal download-prices --out data/market/prices.csv
uv run trading-signal signal --prices data/market/prices.csv --out reports/latest-signal.md
uv run trading-signal backtest \
  --prices data/market/prices.csv \
  --out reports/backtest.md \
  --equity-out reports/equity_curve.csv \
  --trades-out reports/trades.csv
```

## Cron Example

Open the crontab:

```bash
crontab -e
```

Run every Monday at 09:00 Paris time:

```cron
0 9 * * 1 cd /home/pi/agent-trading-signal && uv run trading-signal signal --download --out reports/latest-signal.md
```

## Operational Notes

- Keep generated `data/` and `reports/` folders out of Git.
- Pull updates manually before the weekly run if the strategy code changed.
- Add notification later once the report format is stable.
