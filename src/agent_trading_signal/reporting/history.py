from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from agent_trading_signal.domain import SignalResult
from agent_trading_signal.portfolio import allocation_deltas, needs_rebalance

FIELDNAMES = [
    "generated_at",
    "signal_date",
    "data_source",
    "data_age_days",
    "decision",
    "regime",
    "conviction",
    "current_allocation",
    "target_allocation",
    "leaders",
    "top_rank",
    "top_net_score",
    "warnings",
]


def append_weekly_signal_history(
    path: str | Path,
    result: SignalResult,
    current_allocation: dict[str, float],
    generated_at: datetime,
    data_source: str,
    min_trade_threshold: float = 0.005,
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    should_write_header = not output_path.exists() or output_path.stat().st_size == 0

    deltas = allocation_deltas(
        current_allocation=current_allocation,
        target_allocation=result.allocation,
        min_trade_threshold=min_trade_threshold,
    )
    row = {
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "signal_date": result.as_of.isoformat(),
        "data_source": data_source,
        "data_age_days": (generated_at.date() - result.as_of).days,
        "decision": "rebalance_required" if needs_rebalance(deltas) else "no_trade_needed",
        "regime": result.regime,
        "conviction": result.conviction,
        "current_allocation": _serialize_allocation(current_allocation),
        "target_allocation": _serialize_allocation(result.allocation),
        "leaders": "|".join(result.leaders),
        "top_rank": result.ranks[0].symbol if result.ranks else "",
        "top_net_score": result.ranks[0].net_score if result.ranks else "",
        "warnings": "|".join(result.warnings),
    }

    with output_path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        if should_write_header:
            writer.writeheader()
        writer.writerow(row)


def _serialize_allocation(allocation: dict[str, float]) -> str:
    return "|".join(f"{symbol}:{weight:.6f}" for symbol, weight in allocation.items())
