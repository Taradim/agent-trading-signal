from __future__ import annotations

from datetime import datetime

from agent_trading_signal.domain import BacktestResult, PairStrength, SignalResult
from agent_trading_signal.portfolio import allocation_deltas, needs_rebalance
from agent_trading_signal.reporting.history import LastModelPosition

REGIME_LABELS = {
    "cash_defense": "cash defense",
    "cash_filter": "cash by entry filter",
    "clear_trend": "clear trend",
    "transition": "transition",
    "range": "range / unclear leadership",
}


def render_weekly_decision_report(
    result: SignalResult,
    last_position: LastModelPosition | None,
    generated_at: datetime,
    data_source: str,
    min_trade_threshold: float = 0.005,
) -> str:
    previous_allocation = last_position.allocation if last_position else result.allocation
    deltas = allocation_deltas(
        current_allocation=previous_allocation,
        target_allocation=result.allocation,
        min_trade_threshold=min_trade_threshold,
    )
    position_changed = last_position is not None and needs_rebalance(deltas)
    data_age_days = (generated_at.date() - result.as_of).days

    lines: list[str] = []
    lines.append(f"# Weekly Decision Report - {result.as_of.isoformat()}")
    lines.append("")
    lines.append(f"**Generated:** {generated_at.isoformat(timespec='seconds')}")
    lines.append(f"**Price data as of:** {result.as_of.isoformat()}")
    lines.append(f"**Data source:** {data_source}")
    lines.append(f"**Data age:** {data_age_days} calendar days")
    lines.append(f"**Decision:** {_decision_label(last_position, position_changed)}")
    lines.append(f"**Regime:** {REGIME_LABELS[result.regime]}")
    lines.append(f"**Conviction:** {result.conviction}")
    if last_position is not None:
        position_age_days = (generated_at.date() - last_position.since).days
        lines.append(
            f"**Last model position:** {_format_allocation(last_position.allocation)} "
            f"since {last_position.since.isoformat()} ({_format_age(position_age_days)})"
        )
    else:
        lines.append("**Last model position:** none (initial signal)")
    lines.append(f"**Target allocation:** {_format_allocation(result.allocation)}")
    lines.append("")

    if data_age_days > 4:
        lines.append(
            "> Price data is older than four calendar days. Refresh prices before trading."
        )
        lines.append("")

    lines.append("## Trade Plan")
    lines.append("")
    lines.append("| Asset | Last position | Target | Change | Action |")
    lines.append("| --- | ---: | ---: | ---: | --- |")
    for delta in deltas:
        lines.append(
            "| "
            f"{delta.symbol} | {delta.current_weight:.2%} | {delta.target_weight:.2%} | "
            f"{delta.delta:+.2%} | {delta.action} |"
        )
    lines.append("")

    lines.append("## Model Read")
    lines.append("")
    lines.append(_quick_read(result))
    lines.append("")

    lines.append("## Why This Target")
    lines.append("")
    lines.append(_leader_rationale(result))
    lines.append("")

    if result.warnings:
        lines.append("## Watchpoints")
        lines.append("")
        for warning in result.warnings:
            lines.append(f"- {warning}")
        lines.append("")

    lines.append("## Relative Strength Ranking")
    lines.append("")
    lines.append("| Rank | Asset | Net | Wins | Losses | Neutral | Absolute trend | Price |")
    lines.append("| ---: | --- | ---: | ---: | ---: | ---: | --- | ---: |")
    for index, rank in enumerate(result.ranks, start=1):
        lines.append(
            "| "
            f"{index} | {rank.symbol} | {rank.net_score} | {rank.wins} | "
            f"{rank.losses} | {rank.neutral} | {rank.trend.label} | "
            f"{rank.trend.price:.2f} |"
        )
    lines.append("")

    lines.append("## Absolute Trend")
    lines.append("")
    lines.append("| Asset | Price | EMA35 | SMA100 | SMA200 | State |")
    lines.append("| --- | ---: | ---: | ---: | ---: | --- |")
    for symbol, trend in result.trends.items():
        lines.append(
            "| "
            f"{symbol} | {trend.price:.2f} | {trend.ema35:.2f} | "
            f"{trend.sma100:.2f} | {trend.sma200:.2f} | {trend.label} |"
        )
    lines.append("")

    return "\n".join(lines)


def render_weekly_notification(
    result: SignalResult,
    last_position: LastModelPosition | None,
    generated_at: datetime,
    min_trade_threshold: float = 0.005,
) -> str:
    previous_allocation = last_position.allocation if last_position else result.allocation
    deltas = allocation_deltas(
        current_allocation=previous_allocation,
        target_allocation=result.allocation,
        min_trade_threshold=min_trade_threshold,
    )
    position_changed = last_position is not None and needs_rebalance(deltas)
    data_age_days = (generated_at.date() - result.as_of).days
    action_lines = [
        f"{delta.action.upper()} {delta.symbol} {delta.delta:+.2%}"
        for delta in deltas
        if delta.action != "hold"
    ]
    watchpoints = result.warnings[:3]

    lines = [
        f"Weekly Trading Signal - {result.as_of.isoformat()}",
        f"Decision: {_decision_label(last_position, position_changed)}",
        f"Target: {_format_allocation(result.allocation)}",
        f"Regime: {REGIME_LABELS[result.regime]}",
        f"Conviction: {result.conviction}",
        f"Data age: {data_age_days} calendar days",
    ]
    if last_position is not None:
        position_age_days = (generated_at.date() - last_position.since).days
        lines.append(
            f"Last position: {_format_allocation(last_position.allocation)} since "
            f"{last_position.since.isoformat()} ({_format_age(position_age_days)})"
        )
        if action_lines:
            lines.append("Move: " + "; ".join(action_lines))
        elif last_position.previous_allocation is not None:
            lines.append(
                "Last move: "
                f"{_format_allocation(last_position.previous_allocation)} -> "
                f"{_format_allocation(last_position.allocation)} on "
                f"{last_position.since.isoformat()}"
            )
    else:
        lines.append("Last position: none (initial signal)")
    lines.append("Why: " + _leader_rationale(result))
    if watchpoints:
        lines.append("Watchpoints: " + "; ".join(watchpoints))
    return "\n".join(lines)


def render_signal_report(result: SignalResult) -> str:
    lines: list[str] = []
    lines.append(f"# Weekly Signal - {result.as_of.isoformat()}")
    lines.append("")
    lines.append(f"**Regime:** {REGIME_LABELS[result.regime]}")
    lines.append(f"**Conviction:** {result.conviction}")
    lines.append(f"**Target allocation:** {_format_allocation(result.allocation)}")
    lines.append("")

    if result.warnings:
        lines.append("## Watchpoints")
        lines.append("")
        for warning in result.warnings:
            lines.append(f"- {warning}")
        lines.append("")

    lines.append("## Relative Strength Ranking")
    lines.append("")
    lines.append("| Rank | Asset | Net | Wins | Losses | Neutral | Absolute trend | Price |")
    lines.append("| ---: | --- | ---: | ---: | ---: | ---: | --- | ---: |")
    for index, rank in enumerate(result.ranks, start=1):
        lines.append(
            "| "
            f"{index} | {rank.symbol} | {rank.net_score} | {rank.wins} | "
            f"{rank.losses} | {rank.neutral} | {rank.trend.label} | "
            f"{rank.trend.price:.2f} |"
        )
    lines.append("")

    lines.append("## Absolute Trend")
    lines.append("")
    lines.append("| Asset | Price | EMA35 | SMA100 | SMA200 | State |")
    lines.append("| --- | ---: | ---: | ---: | ---: | --- |")
    for symbol, trend in result.trends.items():
        lines.append(
            "| "
            f"{symbol} | {trend.price:.2f} | {trend.ema35:.2f} | "
            f"{trend.sma100:.2f} | {trend.sma200:.2f} | {trend.label} |"
        )
    lines.append("")

    lines.append("## Most Decisive Ratios")
    lines.append("")
    lines.append("| Ratio | Signal | Points | EMA35 slope 10d |")
    lines.append("| --- | --- | ---: | ---: |")
    decisive_pairs = sorted(result.pairs, key=lambda pair: abs(pair.points), reverse=True)
    for pair in decisive_pairs[:12]:
        lines.append(
            f"| {pair.left}/{pair.right} | {pair.signal} | {pair.points} | {pair.ema35_slope:.2%} |"
        )
    lines.append("")

    lines.append("## Quick Read")
    lines.append("")
    lines.append(_quick_read(result))
    lines.append("")

    return "\n".join(lines)


def render_backtest_report(result: BacktestResult) -> str:
    lines: list[str] = []
    metrics = result.metrics
    lines.append("# Backtest Report")
    lines.append("")
    lines.append("## Strategy Metrics")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | ---: |")
    lines.append(f"| Total return | {metrics.total_return:.2%} |")
    lines.append(f"| CAGR | {metrics.cagr:.2%} |")
    lines.append(f"| Max drawdown | {metrics.max_drawdown:.2%} |")
    lines.append(f"| Volatility | {metrics.volatility:.2%} |")
    lines.append(f"| Trades | {metrics.trade_count} |")
    lines.append(f"| Average turnover | {metrics.average_turnover:.2%} |")
    lines.append(f"| Time in cash | {metrics.time_in_cash:.2%} |")
    lines.append("")

    if result.benchmark_curves:
        lines.append("## Benchmarks")
        lines.append("")
        lines.append("| Benchmark | Total return |")
        lines.append("| --- | ---: |")
        for symbol, curve in result.benchmark_curves.items():
            total_return = curve.iloc[-1] / curve.iloc[0] - 1.0
            lines.append(f"| {symbol} | {total_return:.2%} |")
        lines.append("")

    lines.append("## Trades")
    lines.append("")
    lines.append(
        "| Signal date | Execution date | Allocation | Turnover | Cost | Regime | Conviction |"
    )
    lines.append("| --- | --- | --- | ---: | ---: | --- | --- |")
    for trade in result.trades:
        lines.append(
            "| "
            f"{trade.signal_date.isoformat()} | {trade.execution_date.isoformat()} | "
            f"{_format_allocation(trade.allocation)} | {trade.turnover:.2%} | "
            f"{trade.cost:.2f} | {REGIME_LABELS[trade.regime]} | {trade.conviction} |"
        )
    lines.append("")
    return "\n".join(lines)


def _format_allocation(allocation: dict[str, float]) -> str:
    return ", ".join(f"{symbol} {weight:.2%}" for symbol, weight in allocation.items())


def _decision_label(
    last_position: LastModelPosition | None,
    position_changed: bool,
) -> str:
    if last_position is None:
        return "initial signal"
    return "position change" if position_changed else "no position change"


def _format_age(days: int) -> str:
    days = max(days, 0)
    if days == 0:
        return "today"
    weeks, remaining_days = divmod(days, 7)
    parts: list[str] = []
    if weeks:
        parts.append(f"{weeks} week{'s' if weeks != 1 else ''}")
    if remaining_days:
        parts.append(f"{remaining_days} day{'s' if remaining_days != 1 else ''}")
    return ", ".join(parts)


def _leader_rationale(result: SignalResult) -> str:
    if result.allocation == {"CASH": 1.0}:
        cash_reason = "No active asset passes the entry filter, so the target is CASH."
        return f"{result.rotation_note} {cash_reason}" if result.rotation_note else cash_reason
    if not result.leaders or not result.ranks:
        return "No ranked leader is available."

    leader = result.leaders[0]
    leader_rank = next(rank for rank in result.ranks if rank.symbol == leader)
    leader_position = next(
        index for index, rank in enumerate(result.ranks, start=1) if rank.symbol == leader
    )
    proposed_symbols = [
        symbol
        for symbol, weight in (result.proposed_allocation or result.allocation).items()
        if symbol != "CASH" and weight > 0
    ]
    comparison_symbol = next(
        (symbol for symbol in proposed_symbols if symbol != leader),
        None,
    )
    if comparison_symbol is None:
        comparison_symbol = next(
            (rank.symbol for rank in result.ranks if rank.symbol != leader),
            None,
        )
    runner_up = next(
        (rank for rank in result.ranks if rank.symbol == comparison_symbol),
        None,
    )
    leader_wins = _winning_opponents(leader, result.pairs)
    prefix = f"{result.rotation_note} " if result.rotation_note else ""
    rank_label = (
        f"{leader} ranks first"
        if leader_position == 1
        else f"{leader}, the accepted target, ranks #{leader_position} in the raw tournament"
    )
    rationale = prefix + (
        f"{rank_label} with {leader_rank.wins} win"
        f"{'s' if leader_rank.wins != 1 else ''} and {leader_rank.losses} loss"
        f"{'es' if leader_rank.losses != 1 else ''}"
    )
    if leader_wins:
        rationale += f" (against {', '.join(leader_wins)})"
    rationale += "."

    if runner_up is None:
        return rationale

    runner_wins = _winning_opponents(runner_up.symbol, result.pairs)
    runner_position = next(
        index for index, rank in enumerate(result.ranks, start=1) if rank.symbol == runner_up.symbol
    )
    runner_label = (
        f"{runner_up.symbol} is the raw leader"
        if runner_position == 1
        else f"{runner_up.symbol} ranks #{runner_position}"
    )
    rationale += (
        f" {runner_label} with {runner_up.wins} win"
        f"{'s' if runner_up.wins != 1 else ''} and {runner_up.losses} loss"
        f"{'es' if runner_up.losses != 1 else ''}"
    )
    if runner_wins:
        rationale += f" (against {', '.join(runner_wins)})"
    rationale += "."

    direct_pair = _find_pair(leader, runner_up.symbol, result.pairs)
    if direct_pair is not None:
        rationale += (
            f" Their direct {direct_pair.left}/{direct_pair.right} ratio is "
            f"{direct_pair.signal}: {_relative_position(direct_pair.ratio, direct_pair.ema35)} "
            f"EMA35, {_relative_position(direct_pair.ratio, direct_pair.sma100)} SMA100, "
            f"{_relative_position(direct_pair.ratio, direct_pair.sma200)} SMA200, "
            f"EMA35 slope {direct_pair.ema35_slope:+.2%} over 10 sessions."
        )
    return rationale


def _winning_opponents(symbol: str, pairs: list[PairStrength]) -> list[str]:
    opponents: list[str] = []
    for pair in pairs:
        if pair.left == symbol and pair.signal == "win":
            opponents.append(pair.right)
        elif pair.right == symbol and pair.signal == "loss":
            opponents.append(pair.left)
    return opponents


def _find_pair(
    left: str,
    right: str,
    pairs: list[PairStrength],
) -> PairStrength | None:
    return next(
        (pair for pair in pairs if {pair.left, pair.right} == {left, right}),
        None,
    )


def _relative_position(value: float, reference: float) -> str:
    return "above" if value > reference else "below"


def _quick_read(result: SignalResult) -> str:
    if result.regime == "cash_defense":
        return (
            "Every tracked asset is below EMA35, SMA100, and SMA200. "
            "The model therefore prefers 100% cash."
        )
    if result.regime == "cash_filter":
        return (
            "No active asset passes the entry filter. The model therefore prefers cash "
            "until at least one asset reclaims its SMA200."
        )

    leaders = ", ".join(result.leaders)
    if result.conviction == "high":
        return f"Relative leadership is clear. The target portfolio favors {leaders}."
    if result.regime == "range":
        return (
            f"Leadership is unclear. The model proposes {leaders}, "
            "but conviction is low and false-signal risk is elevated."
        )
    return (
        f"The signal points to {leaders} in a transition regime. "
        "This is the kind of setup where equal-weight split allocations can reduce regret."
    )
