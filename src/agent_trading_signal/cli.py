from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Annotated

import pandas as pd
import typer

from agent_trading_signal.backtest.engine import run_weekly_backtest
from agent_trading_signal.backtest.export import write_equity_curve, write_trades
from agent_trading_signal.backtest.scenarios import research_scenarios, run_scenarios
from agent_trading_signal.data.csv_prices import load_price_csv, save_price_csv
from agent_trading_signal.data.yfinance_provider import download_adjusted_closes
from agent_trading_signal.notifications.telegram import (
    send_telegram_message,
    telegram_config_from_env,
)
from agent_trading_signal.portfolio import validate_portfolio_symbols
from agent_trading_signal.reporting.excel import write_scenario_workbook
from agent_trading_signal.reporting.history import (
    LastModelPosition,
    append_weekly_signal_history,
    load_last_model_position,
)
from agent_trading_signal.reporting.markdown import (
    render_backtest_report,
    render_signal_report,
    render_weekly_decision_report,
    render_weekly_notification,
)
from agent_trading_signal.settings import (
    AssetConfig,
    load_portfolio,
    load_strategy_config,
    load_universe,
)
from agent_trading_signal.strategy.relative_strength import evaluate_relative_strength
from agent_trading_signal.strategy.rotation import apply_rotation_policy

app = typer.Typer(help="Relative-strength trading signal toolkit.")
DEFAULT_UNIVERSE_PATH = Path("config/universe.toml")
DEFAULT_STRATEGY_PATH = Path("config/strategy.toml")
DEFAULT_PRICE_PATH = Path("data/market/prices.csv")
DEFAULT_BACKTEST_REPORT_PATH = Path("reports/backtest.md")
DEFAULT_ANALYSIS_WORKBOOK_PATH = Path("reports/strategy_analysis.xlsx")
DEFAULT_RECOMMENDED_UNIVERSE_PATH = Path("config/universe_recommended.toml")
DEFAULT_RECOMMENDED_STRATEGY_PATH = Path("config/strategy_recommended.toml")
DEFAULT_RECOMMENDED_PRICE_PATH = Path("data/market/recommended_prices.csv")
DEFAULT_PORTFOLIO_PATH = Path("config/current_portfolio.toml")
DEFAULT_WEEKLY_REPORT_PATH = Path("reports/weekly_decision.md")
DEFAULT_WEEKLY_HISTORY_PATH = Path("reports/history/model_positions.csv")


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


@app.command()
def weekly_report(
    prices: Annotated[
        Path | None,
        typer.Option(help="CSV file to read when --no-download is used."),
    ] = DEFAULT_RECOMMENDED_PRICE_PATH,
    universe: Annotated[
        Path,
        typer.Option(help="Universe TOML file."),
    ] = DEFAULT_RECOMMENDED_UNIVERSE_PATH,
    strategy_config: Annotated[
        Path,
        typer.Option(help="Strategy TOML file."),
    ] = DEFAULT_RECOMMENDED_STRATEGY_PATH,
    portfolio: Annotated[
        Path,
        typer.Option(help="One-time bootstrap position when model history is empty."),
    ] = DEFAULT_PORTFOLIO_PATH,
    out: Annotated[
        Path | None,
        typer.Option(help="Markdown output path."),
    ] = DEFAULT_WEEKLY_REPORT_PATH,
    download: Annotated[
        bool,
        typer.Option(help="Download fresh prices before generating the report."),
    ] = True,
    prices_out: Annotated[
        Path | None,
        typer.Option(help="Optional CSV path where downloaded prices are saved."),
    ] = DEFAULT_RECOMMENDED_PRICE_PATH,
    history_out: Annotated[
        Path | None,
        typer.Option(help="Optional CSV path where the weekly run history is appended."),
    ] = DEFAULT_WEEKLY_HISTORY_PATH,
    exclude: Annotated[
        list[str] | None,
        typer.Option("--exclude", help="Asset symbol to exclude from this run."),
    ] = None,
    min_trade_threshold: Annotated[
        float,
        typer.Option(help="Minimum allocation change shown as a trade."),
    ] = 0.005,
    notify: Annotated[
        bool,
        typer.Option(help="Send a Telegram notification after generating the report."),
    ] = False,
    notification_dry_run: Annotated[
        bool,
        typer.Option(help="Print the Telegram notification text without sending it."),
    ] = False,
    notification_timeout_seconds: Annotated[
        float,
        typer.Option(help="Telegram API timeout in seconds."),
    ] = 10.0,
) -> None:
    """Generate the recommended weekly decision report."""
    universe_config = load_universe(universe)
    config = load_strategy_config(strategy_config)
    last_position = load_last_model_position(history_out) if history_out is not None else None
    if last_position is None and portfolio.exists():
        bootstrap = load_portfolio(portfolio)
        validate_portfolio_symbols(bootstrap.allocation, universe_config.symbols)
        last_position = LastModelPosition(
            allocation=bootstrap.allocation,
            since=datetime.fromtimestamp(portfolio.stat().st_mtime).astimezone().date(),
            previous_allocation=None,
        )

    assets = universe_config.active_assets(exclude)
    start = _default_signal_start(config.signal.sma_slow_window)
    price_frame = _load_prices(
        prices=prices,
        download=download,
        assets=assets,
        start=start,
        end=None,
    )
    if download and prices_out is not None:
        save_price_csv(price_frame, prices_out)
        typer.echo(f"Saved {len(price_frame)} rows to {prices_out}")

    raw_result = evaluate_relative_strength(price_frame, assets, config.signal)
    data_source = "yfinance download" if download else str(prices)
    generated_at = datetime.now().astimezone()
    result = apply_rotation_policy(
        signal=raw_result,
        incumbent_allocation=last_position.allocation if last_position else None,
        incumbent_since=last_position.since if last_position else None,
        evaluation_date=generated_at.date(),
        signal_config=config.signal,
        min_holding_days=config.backtest.min_holding_days,
    )
    report = render_weekly_decision_report(
        result=result,
        last_position=last_position,
        generated_at=generated_at,
        data_source=data_source,
        min_trade_threshold=min_trade_threshold,
    )
    _write_or_print(report, out)
    if history_out is not None:
        append_weekly_signal_history(
            path=history_out,
            result=result,
            generated_at=generated_at,
            data_source=data_source,
            min_trade_threshold=min_trade_threshold,
        )
        typer.echo(f"Appended weekly history to {history_out}")

    if notify or notification_dry_run:
        notification = render_weekly_notification(
            result=result,
            last_position=last_position,
            generated_at=generated_at,
            min_trade_threshold=min_trade_threshold,
        )
        if notification_dry_run:
            typer.echo("")
            typer.echo("Telegram notification preview:")
            typer.echo(notification)
        if notify:
            try:
                telegram_config = telegram_config_from_env()
                send_telegram_message(
                    config=telegram_config,
                    text=notification,
                    timeout_seconds=notification_timeout_seconds,
                )
            except (RuntimeError, ValueError) as error:
                typer.echo(f"Notification failed: {error}", err=True)
                raise typer.Exit(1) from error
            typer.echo("Sent Telegram notification")


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
