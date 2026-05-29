from __future__ import annotations

from agent_trading_signal.domain import BacktestResult, SignalResult

REGIME_LABELS = {
    "cash_defense": "cash defense",
    "cash_filter": "cash by entry filter",
    "clear_trend": "clear trend",
    "transition": "transition",
    "range": "range / unclear leadership",
    "stabilized_range": "stabilized range",
}


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
    if result.regime == "stabilized_range":
        return (
            f"Recent leadership has been alternating. The model proposes a {leaders} split "
            "instead of forcing another 100% switch."
        )
    return (
        f"The signal points to {leaders} in a transition regime. "
        "This is the kind of setup where equal-weight split allocations can reduce regret."
    )
