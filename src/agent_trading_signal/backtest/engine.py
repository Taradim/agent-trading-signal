from __future__ import annotations

from dataclasses import replace
from itertools import pairwise
from math import sqrt

import pandas as pd
from pandas.tseries.offsets import BDay

from agent_trading_signal.domain import (
    AssetRank,
    BacktestMetrics,
    BacktestResult,
    SignalResult,
    Trade,
)
from agent_trading_signal.settings import AssetConfig, BacktestConfig, SignalConfig
from agent_trading_signal.strategy.relative_strength import evaluate_relative_strength


def run_weekly_backtest(
    prices: pd.DataFrame,
    assets: list[AssetConfig],
    signal_config: SignalConfig,
    backtest_config: BacktestConfig,
) -> BacktestResult:
    full_prices = _require_history(prices.sort_index().dropna(how="any"), signal_config)
    returns = full_prices.pct_change().fillna(0.0)
    decision_dates = _decision_dates(full_prices, backtest_config.decision_frequency)
    scheduled_trades = _build_scheduled_trades(
        full_prices=full_prices,
        decision_dates=decision_dates,
        assets=assets,
        signal_config=signal_config,
        backtest_config=backtest_config,
    )
    scheduled_trades = _apply_flip_flop_stabilizer(scheduled_trades, signal_config)

    start_index = full_prices.index.searchsorted(pd.Timestamp(backtest_config.start))
    simulation_dates = full_prices.index[start_index:]
    if simulation_dates.empty:
        raise ValueError("No simulation dates available")

    current_allocation: dict[str, float] = {"CASH": 1.0}
    current_capital = backtest_config.initial_capital
    last_rebalance_date: pd.Timestamp | None = None
    trades: list[Trade] = []
    equity_values: list[float] = []
    cash_flags: list[bool] = []

    trades_by_execution = _group_trades_by_execution(scheduled_trades)
    total_cost_bps = backtest_config.transaction_cost_bps + backtest_config.slippage_bps

    previous_date: pd.Timestamp | None = None
    for current_date in simulation_dates:
        if previous_date is not None:
            current_capital *= 1.0 + _portfolio_return(
                returns.loc[current_date],
                current_allocation,
            )

        if current_date in trades_by_execution:
            signal = trades_by_execution[current_date]
            desired_allocation = signal.allocation
            if _should_execute_trade(
                current_allocation=current_allocation,
                desired_allocation=desired_allocation,
                signal=signal,
                last_rebalance_date=last_rebalance_date,
                execution_date=current_date,
                backtest_config=backtest_config,
            ):
                turnover = _one_way_turnover(current_allocation, desired_allocation)
                cost = current_capital * turnover * (total_cost_bps / 10000.0)
                current_capital -= cost
                current_allocation = desired_allocation
                last_rebalance_date = current_date
                trades.append(
                    Trade(
                        signal_date=signal.as_of,
                        execution_date=current_date.date(),
                        allocation=desired_allocation,
                        turnover=turnover,
                        cost=cost,
                        capital_after_cost=current_capital,
                        regime=signal.regime,
                        conviction=signal.conviction,
                    )
                )

        equity_values.append(current_capital)
        cash_flags.append(current_allocation == {"CASH": 1.0})
        previous_date = current_date

    equity_curve = pd.Series(equity_values, index=simulation_dates, name="strategy")
    benchmark_curves = _benchmark_curves(full_prices.loc[simulation_dates], backtest_config)
    return BacktestResult(
        equity_curve=equity_curve,
        trades=trades,
        metrics=_metrics(equity_curve, trades, cash_flags),
        benchmark_curves=benchmark_curves,
    )


def _require_history(prices: pd.DataFrame, signal_config: SignalConfig) -> pd.DataFrame:
    if len(prices) < signal_config.min_observations:
        raise ValueError(
            f"At least {signal_config.min_observations} price observations are required"
        )
    return prices


def _decision_dates(prices: pd.DataFrame, frequency: str) -> list[pd.Timestamp]:
    grouped = prices.resample(frequency).last().dropna(how="all")
    dates: list[pd.Timestamp] = []
    for period_end in grouped.index:
        eligible = prices.index[prices.index <= period_end]
        if not eligible.empty:
            dates.append(eligible[-1])
    return sorted(set(dates))


def _build_scheduled_trades(
    full_prices: pd.DataFrame,
    decision_dates: list[pd.Timestamp],
    assets: list[AssetConfig],
    signal_config: SignalConfig,
    backtest_config: BacktestConfig,
) -> list[tuple[pd.Timestamp, SignalResult]]:
    scheduled: list[tuple[pd.Timestamp, SignalResult]] = []
    for decision_date in decision_dates:
        history = full_prices.loc[:decision_date]
        if len(history) < signal_config.min_observations:
            continue
        signal = evaluate_relative_strength(history, assets, signal_config)
        execution_date = _execution_date(
            full_prices.index,
            decision_date,
            backtest_config.execution_lag_business_days,
        )
        if execution_date is not None:
            scheduled.append((execution_date, signal))
    return scheduled


def _apply_flip_flop_stabilizer(
    scheduled_trades: list[tuple[pd.Timestamp, SignalResult]],
    signal_config: SignalConfig,
) -> list[tuple[pd.Timestamp, SignalResult]]:
    if not signal_config.use_flip_flop_stabilizer:
        return scheduled_trades

    stabilized: list[tuple[pd.Timestamp, SignalResult]] = []
    recent_single_leaders: list[str] = []
    active_pair: tuple[str, str] | None = None
    for execution_date, signal in scheduled_trades:
        if active_pair and _flip_flop_pair_can_stay_active(signal, active_pair, signal_config):
            adjusted_signal = _blend_flip_flop_pair(
                signal=signal,
                symbols=active_pair,
                warning=(
                    "Flip-flop stabilizer keeps "
                    f"{active_pair[0]}/{active_pair[1]} at 50/50 while scores remain close."
                ),
            )
        else:
            active_pair = None
            adjusted_signal = _stabilize_flip_flop_signal(
                signal, recent_single_leaders, signal_config
            )
            if adjusted_signal.regime == "stabilized_range":
                active_pair = tuple(adjusted_signal.allocation)

        stabilized.append((execution_date, adjusted_signal))

        raw_single_leader = _single_asset_allocation(signal.allocation)
        if raw_single_leader is not None:
            recent_single_leaders.append(raw_single_leader)
            recent_single_leaders = recent_single_leaders[
                -(signal_config.flip_flop_lookback_signals - 1) :
            ]

    return stabilized


def _stabilize_flip_flop_signal(
    signal: SignalResult,
    recent_single_leaders: list[str],
    signal_config: SignalConfig,
) -> SignalResult:
    current_leader = _single_asset_allocation(signal.allocation)
    if current_leader is None:
        return signal

    leader_window = (recent_single_leaders + [current_leader])[
        -signal_config.flip_flop_lookback_signals :
    ]
    if len(set(leader_window)) != 2:
        return signal

    switch_count = sum(left != right for left, right in pairwise(leader_window))
    if switch_count < signal_config.flip_flop_min_switches:
        return signal

    symbols = _ranked_pair(tuple(leader_window), signal.ranks)
    if not _flip_flop_pair_is_eligible(symbols, signal.ranks, signal_config):
        return signal

    if _flip_flop_pair_score_gap(symbols, signal.ranks) > _flip_flop_maximum_gap(signal_config):
        return signal

    warning = (
        "Flip-flop stabilizer blends "
        f"{symbols[0]}/{symbols[1]} after {switch_count} switches "
        f"in the last {len(leader_window)} signals."
    )
    return _blend_flip_flop_pair(signal, symbols, warning)


def _flip_flop_pair_can_stay_active(
    signal: SignalResult,
    symbols: tuple[str, str],
    signal_config: SignalConfig,
) -> bool:
    current_leader = _single_asset_allocation(signal.allocation)
    if current_leader not in symbols:
        return False
    if not _flip_flop_pair_is_eligible(symbols, signal.ranks, signal_config):
        return False
    return _flip_flop_pair_score_gap(symbols, signal.ranks) <= _flip_flop_maximum_gap(signal_config)


def _blend_flip_flop_pair(
    signal: SignalResult,
    symbols: tuple[str, str],
    warning: str,
) -> SignalResult:
    ranked_symbols = _ranked_pair(symbols, signal.ranks)
    return replace(
        signal,
        allocation={ranked_symbols[0]: 0.5, ranked_symbols[1]: 0.5},
        regime="stabilized_range",
        conviction="medium",
        warnings=[*signal.warnings, warning],
    )


def _single_asset_allocation(allocation: dict[str, float]) -> str | None:
    if len(allocation) != 1:
        return None
    symbol, weight = next(iter(allocation.items()))
    if symbol == "CASH" or abs(weight - 1.0) > 1e-9:
        return None
    return symbol


def _flip_flop_pair_is_eligible(
    symbols: tuple[str, str],
    ranks: list[AssetRank],
    signal_config: SignalConfig,
) -> bool:
    rank_by_symbol = {rank.symbol: rank for rank in ranks}
    for symbol in symbols:
        rank = rank_by_symbol[symbol]
        if signal_config.require_above_sma200_for_entries and not rank.trend.above_sma200:
            return False
        if not signal_config.require_above_sma200_for_entries and rank.trend.is_downtrend:
            return False
    return True


def _ranked_pair(symbols: tuple[str, ...], ranks: list[AssetRank]) -> tuple[str, str]:
    score_by_symbol = {rank.symbol: rank.net_score for rank in ranks}
    ranked = sorted(set(symbols), key=lambda symbol: score_by_symbol[symbol], reverse=True)
    return ranked[0], ranked[1]


def _flip_flop_pair_score_gap(symbols: tuple[str, str], ranks: list[AssetRank]) -> int:
    score_by_symbol = {rank.symbol: rank.net_score for rank in ranks}
    return abs(score_by_symbol[symbols[0]] - score_by_symbol[symbols[1]])


def _flip_flop_maximum_gap(signal_config: SignalConfig) -> int:
    return signal_config.tie_tolerance + signal_config.flip_flop_tie_tolerance_boost


def _execution_date(
    index: pd.DatetimeIndex,
    signal_date: pd.Timestamp,
    lag_business_days: int,
) -> pd.Timestamp | None:
    target = signal_date + BDay(lag_business_days)
    position = index.searchsorted(target)
    if position >= len(index):
        return None
    return index[position]


def _group_trades_by_execution(
    scheduled_trades: list[tuple[pd.Timestamp, SignalResult]],
) -> dict[pd.Timestamp, SignalResult]:
    grouped: dict[pd.Timestamp, SignalResult] = {}
    for execution_date, signal in scheduled_trades:
        grouped[execution_date] = signal
    return grouped


def _portfolio_return(day_returns: pd.Series, allocation: dict[str, float]) -> float:
    return sum(
        weight * float(day_returns.get(symbol, 0.0)) for symbol, weight in allocation.items()
    )


def _should_execute_trade(
    current_allocation: dict[str, float],
    desired_allocation: dict[str, float],
    signal: SignalResult,
    last_rebalance_date: pd.Timestamp | None,
    execution_date: pd.Timestamp,
    backtest_config: BacktestConfig,
) -> bool:
    if _allocations_equal(current_allocation, desired_allocation):
        return False
    if desired_allocation == {"CASH": 1.0}:
        return True
    if signal.regime == "stabilized_range" and _allocations_overlap(
        current_allocation, desired_allocation
    ):
        return True
    if last_rebalance_date is None or current_allocation == {"CASH": 1.0}:
        return True
    days_held = (execution_date.date() - last_rebalance_date.date()).days
    if days_held >= backtest_config.min_holding_days:
        return True
    return signal.conviction == "high"


def _allocations_equal(left: dict[str, float], right: dict[str, float]) -> bool:
    symbols = set(left) | set(right)
    return all(abs(left.get(symbol, 0.0) - right.get(symbol, 0.0)) < 1e-9 for symbol in symbols)


def _allocations_overlap(left: dict[str, float], right: dict[str, float]) -> bool:
    return any(
        symbol != "CASH" and left.get(symbol, 0.0) > 0 and right.get(symbol, 0.0) > 0
        for symbol in set(left) | set(right)
    )


def _one_way_turnover(left: dict[str, float], right: dict[str, float]) -> float:
    symbols = set(left) | set(right)
    return 0.5 * sum(abs(left.get(symbol, 0.0) - right.get(symbol, 0.0)) for symbol in symbols)


def _benchmark_curves(
    prices: pd.DataFrame,
    backtest_config: BacktestConfig,
) -> dict[str, pd.Series]:
    curves: dict[str, pd.Series] = {}
    for symbol in backtest_config.benchmarks:
        if symbol not in prices.columns:
            continue
        normalized = prices[symbol] / prices[symbol].iloc[0] * backtest_config.initial_capital
        curves[symbol] = normalized.rename(symbol)
    return curves


def _metrics(
    equity_curve: pd.Series,
    trades: list[Trade],
    cash_flags: list[bool],
) -> BacktestMetrics:
    total_return = equity_curve.iloc[-1] / equity_curve.iloc[0] - 1.0
    days = max((equity_curve.index[-1].date() - equity_curve.index[0].date()).days, 1)
    cagr = (equity_curve.iloc[-1] / equity_curve.iloc[0]) ** (365.25 / days) - 1.0
    drawdown = equity_curve / equity_curve.cummax() - 1.0
    daily_returns = equity_curve.pct_change().dropna()
    volatility = float(daily_returns.std() * sqrt(252)) if not daily_returns.empty else 0.0
    average_turnover = sum(trade.turnover for trade in trades) / len(trades) if trades else 0.0
    time_in_cash = sum(cash_flags) / len(cash_flags) if cash_flags else 0.0
    return BacktestMetrics(
        total_return=float(total_return),
        cagr=float(cagr),
        max_drawdown=float(drawdown.min()),
        volatility=volatility,
        trade_count=len(trades),
        average_turnover=average_turnover,
        time_in_cash=time_in_cash,
    )
