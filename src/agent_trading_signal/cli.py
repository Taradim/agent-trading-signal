from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Annotated

import pandas as pd
import typer

from agent_trading_signal.backtest.engine import run_weekly_backtest
from agent_trading_signal.backtest.export import write_equity_curve, write_trades
from agent_trading_signal.backtest.scenarios import research_scenarios, run_scenarios
from agent_trading_signal.data.csv_prices import load_price_csv, save_price_csv
from agent_trading_signal.data.yfinance_provider import download_adjusted_closes
from agent_trading_signal.reporting.excel import write_scenario_workbook
from agent_trading_signal.reporting.markdown import render_backtest_report, render_signal_report
from agent_trading_signal.settings import AssetConfig, load_strategy_config, load_universe
from agent_trading_signal.strategy.relative_strength import evaluate_relative_strength

app = typer.Typer(help="Relative-strength trading signal toolkit.")
DEFAULT_UNIVERSE_PATH = Path("config/universe.toml")
DEFAULT_STRATEGY_PATH = Path("config/strategy.toml")
DEFAULT_PRICE_PATH = Path("data/market/prices.csv")
DEFAULT_BACKTEST_REPORT_PATH = Path("reports/backtest.md")
DEFAULT_ANALYSIS_WORKBOOK_PATH = Path("reports/strategy_analysis.xlsx")


@app.command()
def signal(
    prices: Annotated[
        Path | None,
        typer.Option(help="CSV file with Date and price columns."),
    ] = None,
    universe: Annotated[Path, typer.Option(help="Universe TOML file.")] = DEFAULT_UNIVERSE_PATH,
    strategy_config: Annotated[
        Path,
        typer.Option(help="Strategy TOML file."),
    ] = DEFAULT_STRATEGY_PATH,
    out: Annotated[Path | None, typer.Option(help="Optional Markdown output path.")] = None,
    download: Annotated[
        bool,
        typer.Option(help="Download prices from yfinance instead of reading CSV."),
    ] = False,
    exclude: Annotated[
        list[str] | None,
        typer.Option("--exclude", help="Asset symbol to exclude from this run."),
    ] = None,
) -> None:
    """Generate the latest weekly signal report."""
    universe_config = load_universe(universe)
    config = load_strategy_config(strategy_config)
    assets = universe_config.active_assets(exclude)
    price_frame = _load_prices(
        prices=prices,
        download=download,
        assets=assets,
        start=_default_signal_start(config.signal.sma_slow_window),
        end=None,
    )
    result = evaluate_relative_strength(price_frame, assets, config.signal)
    _write_or_print(render_signal_report(result), out)


@app.command()
def backtest(
    prices: Annotated[
        Path | None,
        typer.Option(help="CSV file with Date and price columns."),
    ] = None,
    universe: Annotated[Path, typer.Option(help="Universe TOML file.")] = DEFAULT_UNIVERSE_PATH,
    strategy_config: Annotated[
        Path,
        typer.Option(help="Strategy TOML file."),
    ] = DEFAULT_STRATEGY_PATH,
    out: Annotated[
        Path | None,
        typer.Option(help="Markdown output path."),
    ] = DEFAULT_BACKTEST_REPORT_PATH,
    equity_out: Annotated[
        Path | None,
        typer.Option(help="Optional CSV output path for the strategy and benchmark curves."),
    ] = None,
    trades_out: Annotated[
        Path | None,
        typer.Option(help="Optional CSV output path for executed trades."),
    ] = None,
    download: Annotated[
        bool,
        typer.Option(help="Download prices from yfinance instead of reading CSV."),
    ] = False,
    exclude: Annotated[
        list[str] | None,
        typer.Option("--exclude", help="Asset symbol to exclude from this run."),
    ] = None,
) -> None:
    """Run a weekly backtest from the configured start date."""
    universe_config = load_universe(universe)
    config = load_strategy_config(strategy_config)
    assets = universe_config.active_assets(exclude)
    start = config.backtest.start - timedelta(days=config.backtest.lookback_buffer_days)
    price_frame = _load_prices(
        prices=prices,
        download=download,
        assets=assets,
        start=start,
        end=None,
    )
    result = run_weekly_backtest(
        prices=price_frame,
        assets=assets,
        signal_config=config.signal,
        backtest_config=config.backtest,
    )
    _write_or_print(render_backtest_report(result), out)
    if equity_out is not None:
        write_equity_curve(result, equity_out)
        typer.echo(f"Wrote equity curve to {equity_out}")
    if trades_out is not None:
        write_trades(result, trades_out)
        typer.echo(f"Wrote trades to {trades_out}")


@app.command()
def download_prices(
    out: Annotated[Path, typer.Option(help="Output CSV path.")] = DEFAULT_PRICE_PATH,
    universe: Annotated[Path, typer.Option(help="Universe TOML file.")] = DEFAULT_UNIVERSE_PATH,
    strategy_config: Annotated[
        Path,
        typer.Option(help="Strategy TOML file."),
    ] = DEFAULT_STRATEGY_PATH,
    start: Annotated[str | None, typer.Option(help="Download start date as YYYY-MM-DD.")] = None,
    end: Annotated[str | None, typer.Option(help="Download end date as YYYY-MM-DD.")] = None,
    exclude: Annotated[
        list[str] | None,
        typer.Option("--exclude", help="Asset symbol to exclude from this download."),
    ] = None,
) -> None:
    """Download adjusted daily close prices from yfinance."""
    universe_config = load_universe(universe)
    config = load_strategy_config(strategy_config)
    assets = universe_config.active_assets(exclude)
    download_start = _parse_date(start) or (
        config.backtest.start - timedelta(days=config.backtest.lookback_buffer_days)
    )
    price_frame = download_adjusted_closes(
        assets,
        start=download_start,
        end=_parse_date(end),
    )
    save_price_csv(price_frame, out)
    typer.echo(f"Saved {len(price_frame)} rows to {out}")


@app.command()
def compare(
    prices: Annotated[
        Path | None,
        typer.Option(help="CSV file with Date and price columns."),
    ] = None,
    universe: Annotated[Path, typer.Option(help="Universe TOML file.")] = DEFAULT_UNIVERSE_PATH,
    strategy_config: Annotated[
        Path,
        typer.Option(help="Strategy TOML file."),
    ] = DEFAULT_STRATEGY_PATH,
    out: Annotated[
        Path,
        typer.Option(help="Output XLSX workbook path."),
    ] = DEFAULT_ANALYSIS_WORKBOOK_PATH,
    download: Annotated[
        bool,
        typer.Option(help="Download prices from yfinance instead of reading CSV."),
    ] = False,
    research: Annotated[
        bool,
        typer.Option(help="Include extended research scenarios."),
    ] = False,
) -> None:
    """Compare default strategy scenarios and write a formatted Excel workbook."""
    universe_config = load_universe(universe)
    config = load_strategy_config(strategy_config)
    start = config.backtest.start - timedelta(days=config.backtest.lookback_buffer_days)
    price_frame = _load_prices(
        prices=prices,
        download=download,
        assets=universe_config.assets,
        start=start,
        end=None,
    )
    scenarios = run_scenarios(
        prices=price_frame,
        universe=universe_config,
        signal_config=config.signal,
        backtest_config=config.backtest,
        scenario_definitions=research_scenarios() if research else None,
    )
    write_scenario_workbook(scenarios, out)
    typer.echo(f"Wrote scenario workbook to {out}")


def _load_prices(
    prices: Path | None,
    download: bool,
    assets: list[AssetConfig],
    start: date,
    end: date | None,
) -> pd.DataFrame:
    if download:
        return download_adjusted_closes(assets, start=start, end=end)
    if prices is None:
        raise typer.BadParameter("Provide --prices or use --download.")
    return load_price_csv(prices, assets)


def _default_signal_start(sma_slow_window: int) -> date:
    return date.today() - timedelta(days=max(500, sma_slow_window * 3))


def _parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    return date.fromisoformat(value)


def _write_or_print(content: str, out: Path | None) -> None:
    if out is None:
        typer.echo(content)
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    typer.echo(f"Wrote report to {out}")


def main() -> None:
    app()
