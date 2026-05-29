# Agent Trading Signal

Weekly decision-support engine for a relative-strength multi-asset strategy.

The goal is not to predict markets. The goal is to turn a discretionary process
into a repeatable weekly signal:

- compare major assets against each other through price ratios;
- stay invested in the relative leader, or split equally between equivalent leaders;
- move to cash only when the full universe is in absolute downtrend;
- produce a clear report before manual execution.

This repository is intended for research and decision support. It is not
financial advice and it does not place orders.

## Strategy Summary

The initial universe is defined in [`config/universe.toml`](config/universe.toml):

- Bitcoin (`BTC-USD`)
- Ethereum (`ETH-USD`)
- Gold ETF (`GLD`)
- Silver ETF (`SLV`)
- Semiconductor ETF (`SMH`)
- Nasdaq 100 ETF (`QQQ`)
- S&P 500 ETF (`SPY`)

All research tickers are USD-based to keep the relative-strength matrix clean.
Execution tickers can later be mapped to Interactive Brokers instruments.

### Absolute Trend Filter

Each asset is compared against:

- EMA 35
- SMA 100
- SMA 200

If every asset is below all three moving averages, the target allocation becomes
`CASH 100%`.

Otherwise, the engine stays invested and ranks assets by relative strength.

### Relative Strength Matrix

For each pair of assets, the engine computes the ratio `asset A / asset B`.
Each ratio is scored with:

- ratio above EMA 35;
- ratio above SMA 100;
- ratio above SMA 200;
- positive EMA 35 slope over 10 sessions.

The ratio has a small deadband around moving averages and slopes. This avoids
treating flat ranges as meaningful wins or losses.

By default, the model also refuses new entries in assets trading below their own
SMA 200. This keeps relative winners that are still in long-term absolute
downtrend from becoming portfolio leaders.

### Allocation Rules

The portfolio uses equal-weight discrete allocations:

- 1 leader: `100%`
- 2 leaders: `50% / 50%`
- 3 leaders: `33.33%` each
- 4 leaders: `25%` each

No gradual weighting is used.

## Project Structure

```text
.
|-- config/
|   |-- strategy.toml
|   `-- universe.toml
|-- docs/
|   |-- raspberry_pi.md
|   `-- strategy_spec.md
|-- src/agent_trading_signal/
|   |-- backtest/
|   |-- data/
|   |-- reporting/
|   |-- strategy/
|   |-- cli.py
|   |-- domain.py
|   |-- indicators.py
|   `-- settings.py
|-- tests/
|-- pyproject.toml
`-- README.md
```

## Quick Start

### 1. Install dependencies

```bash
uv sync --extra dev
```

### 2. Download daily prices

```bash
uv run trading-signal download-prices --out data/market/prices.csv
```

The initial provider is `yfinance`, which is practical for research and quick
iteration. Treat it as research-grade data, not as an institutional source.

### 3. Generate the latest signal

```bash
uv run trading-signal signal \
  --prices data/market/prices.csv \
  --out reports/latest-signal.md
```

You can also download data directly during the signal run:

```bash
uv run trading-signal signal --download --out reports/latest-signal.md
```

### 4. Run the backtest

```bash
uv run trading-signal backtest \
  --prices data/market/prices.csv \
  --out reports/backtest.md \
  --equity-out reports/equity_curve.csv \
  --trades-out reports/trades.csv
```

To test a narrower universe without editing the TOML file:

```bash
uv run trading-signal backtest \
  --prices data/market/prices.csv \
  --exclude ETH \
  --exclude SLV
```

To compare the default research scenarios and create a formatted Excel workbook:

```bash
uv run trading-signal compare \
  --prices data/market/prices.csv \
  --out reports/strategy_analysis.xlsx
```

The default backtest starts on `2020-01-01` and uses a lookback buffer so moving
averages are already warm when the simulated period starts.

Downloaded mixed crypto/ETF data is aligned to a common close calendar. This
keeps crypto weekend prices from creating simulated ETF trades on weekends or US
market holidays.

Trade CSV exports include realized PnL and return for each holding period. The
comparison workbook also includes a full trade log where outcomes are
color-coded by return (`<-10%`, `-10% to +10%`, `>+10%`) and conviction is
color-coded from low to high.

## Development

```bash
uv run pytest
uv run ruff check .
uv run ruff format .
```

CI runs the same checks on pull requests.

## Raspberry Pi Operation

For a lightweight weekly run on a Raspberry Pi, use `cron` or a `systemd` timer.
See [`docs/raspberry_pi.md`](docs/raspberry_pi.md).

## Roadmap

- Add a richer backtest report with charts.
- Add portfolio-state tracking and "what changed this week" commentary.
- Add optional notifications through email, Telegram, or Discord.
- Add a second data provider for more reliable historical prices.
- Extend the universe with CAC 40, DAX, FTSE, Nikkei, Hang Seng, and Kospi.
