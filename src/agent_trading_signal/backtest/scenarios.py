from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from agent_trading_signal.backtest.engine import run_weekly_backtest
from agent_trading_signal.domain import BacktestResult, Trade
from agent_trading_signal.settings import (
    BacktestConfig,
    SignalConfig,
    UniverseConfig,
)


@dataclass(frozen=True)
class ScenarioDefinition:
    name: str
    require_above_sma200_for_entries: bool
    excluded_symbols: tuple[str, ...] = ()


@dataclass(frozen=True)
class ScenarioBacktest:
    definition: ScenarioDefinition
    result: BacktestResult


def default_scenarios() -> list[ScenarioDefinition]:
    return [
        ScenarioDefinition(
            name="Baseline",
            require_above_sma200_for_entries=False,
        ),
        ScenarioDefinition(
            name="SMA200 filter",
            require_above_sma200_for_entries=True,
        ),
        ScenarioDefinition(
            name="SMA200 ex ETH/SLV",
            require_above_sma200_for_entries=True,
            excluded_symbols=("ETH", "SLV"),
        ),
    ]


def run_scenarios(
    prices: pd.DataFrame,
    universe: UniverseConfig,
    signal_config: SignalConfig,
    backtest_config: BacktestConfig,
    scenario_definitions: list[ScenarioDefinition] | None = None,
) -> list[ScenarioBacktest]:
    scenarios = scenario_definitions or default_scenarios()
    results: list[ScenarioBacktest] = []
    for scenario in scenarios:
        assets = universe.active_assets(list(scenario.excluded_symbols))
        scenario_signal_config = signal_config.model_copy(
            update={"require_above_sma200_for_entries": scenario.require_above_sma200_for_entries}
        )
        result = run_weekly_backtest(
            prices=prices,
            assets=assets,
            signal_config=scenario_signal_config,
            backtest_config=backtest_config,
        )
        results.append(ScenarioBacktest(definition=scenario, result=result))
    return results


def scenario_summary_frame(scenarios: list[ScenarioBacktest]) -> pd.DataFrame:
    rows = []
    for scenario in scenarios:
        metrics = scenario.result.metrics
        equity = scenario.result.equity_curve
        rows.append(
            {
                "Scenario": scenario.definition.name,
                "Start": equity.index[0].date(),
                "End": equity.index[-1].date(),
                "Start Value": equity.iloc[0],
                "End Value": equity.iloc[-1],
                "Total Return": metrics.total_return,
                "CAGR": metrics.cagr,
                "Max Drawdown": metrics.max_drawdown,
                "Volatility": metrics.volatility,
                "Trades": metrics.trade_count,
                "Average Turnover": metrics.average_turnover,
                "Time in Cash": metrics.time_in_cash,
                "Total Cost": sum(trade.cost for trade in scenario.result.trades),
            }
        )
    return pd.DataFrame(rows)


def trade_analysis_frame(scenarios: list[ScenarioBacktest]) -> pd.DataFrame:
    rows = []
    for scenario in scenarios:
        for row in _trade_analysis_rows(scenario.definition.name, scenario.result):
            rows.append({key: value for key, value in row.items() if key != "Allocation Map"})
    return pd.DataFrame(rows)


def worst_trades_frame(scenarios: list[ScenarioBacktest], per_scenario: int = 12) -> pd.DataFrame:
    trades = trade_analysis_frame(scenarios)
    return (
        trades.sort_values("Return")
        .groupby("Scenario", group_keys=False)
        .head(per_scenario)
        .reset_index(drop=True)
    )


def asset_contribution_frame(scenarios: list[ScenarioBacktest]) -> pd.DataFrame:
    rows = []
    for scenario in scenarios:
        for trade in _trade_analysis_rows(scenario.definition.name, scenario.result):
            allocation = trade["Allocation Map"]
            for symbol, weight in allocation.items():
                rows.append(
                    {
                        "Scenario": scenario.definition.name,
                        "Asset": symbol,
                        "Weighted PnL": trade["PnL"] * weight,
                        "Weighted Days": trade["Holding Days"] * weight,
                        "Exposure Count": weight,
                    }
                )

    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    return (
        frame.groupby(["Scenario", "Asset"], as_index=False)
        .agg(
            {
                "Weighted PnL": "sum",
                "Weighted Days": "sum",
                "Exposure Count": "sum",
            }
        )
        .sort_values(["Scenario", "Weighted PnL"])
        .reset_index(drop=True)
    )


def monthly_equity_frame(scenarios: list[ScenarioBacktest]) -> pd.DataFrame:
    if not scenarios:
        return pd.DataFrame()

    frame = pd.DataFrame(index=scenarios[0].result.equity_curve.index)
    for scenario in scenarios:
        frame[scenario.definition.name] = scenario.result.equity_curve

    for symbol, curve in scenarios[0].result.benchmark_curves.items():
        frame[symbol] = curve

    frame = frame.ffill().dropna(how="any")
    frame["Month"] = frame.index.to_period("M").astype(str)
    return frame.groupby("Month", as_index=False).last()


def drawdown_frame(equity_frame: pd.DataFrame, scenario_names: list[str]) -> pd.DataFrame:
    if equity_frame.empty:
        return pd.DataFrame()

    drawdowns = pd.DataFrame({"Month": equity_frame["Month"]})
    for name in scenario_names:
        series = equity_frame[name]
        drawdowns[name] = series / series.cummax() - 1.0
    return drawdowns


def _trade_analysis_rows(scenario_name: str, result: BacktestResult) -> list[dict]:
    rows = []
    for index, trade in enumerate(result.trades):
        entry_capital = trade.capital_after_cost
        if index + 1 < len(result.trades):
            next_trade = result.trades[index + 1]
            exit_date = next_trade.execution_date
            exit_capital_before_next_cost = next_trade.capital_after_cost + next_trade.cost
            exit_reason = "next_trade"
        else:
            exit_date = result.equity_curve.index[-1].date()
            exit_capital_before_next_cost = float(result.equity_curve.iloc[-1])
            exit_reason = "end_of_data"

        pnl = exit_capital_before_next_cost - entry_capital
        realized_return = pnl / entry_capital if entry_capital else 0.0
        rows.append(
            {
                "Scenario": scenario_name,
                "Signal Date": trade.signal_date,
                "Entry Date": trade.execution_date,
                "Exit Date": exit_date,
                "Holding Days": (exit_date - trade.execution_date).days,
                "Allocation": _format_allocation(trade.allocation),
                "Allocation Map": trade.allocation,
                "Primary Asset": _primary_asset(trade),
                "Entry Capital": entry_capital,
                "Exit Capital Before Next Cost": exit_capital_before_next_cost,
                "PnL": pnl,
                "Return": realized_return,
                "Outcome Band": _outcome_band(realized_return),
                "Entry Cost": trade.cost,
                "Regime": trade.regime,
                "Conviction": trade.conviction,
                "Exit Reason": exit_reason,
            }
        )
    return rows


def _format_allocation(allocation: dict[str, float]) -> str:
    return "; ".join(f"{symbol} {weight:.2%}" for symbol, weight in allocation.items())


def _primary_asset(trade: Trade) -> str:
    if not trade.allocation:
        return ""
    return max(trade.allocation, key=trade.allocation.get)


def _outcome_band(realized_return: float) -> str:
    if realized_return < -0.10:
        return "Loss below -10%"
    if realized_return > 0.10:
        return "Gain above +10%"
    return "Between -10% and +10%"
