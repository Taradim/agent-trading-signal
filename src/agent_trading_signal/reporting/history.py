from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
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
    "proposed_allocation",
    "rotation_note",
    "leaders",
    "top_rank",
    "top_net_score",
    "warnings",
]


@dataclass(frozen=True)
class LastModelPosition:
    allocation: dict[str, float]
    since: date
    previous_allocation: dict[str, float] | None


def load_last_model_position(path: str | Path) -> LastModelPosition | None:
    history_path = Path(path)
    if not history_path.exists() or history_path.stat().st_size == 0:
        return None

    positions: list[tuple[date, dict[str, float]]] = []
    with history_path.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            serialized = row.get("target_allocation", "")
            generated_at = row.get("generated_at", "")
            signal_date = row.get("signal_date", "")
            if not serialized or not (generated_at or signal_date):
                continue
            move_date = (
                datetime.fromisoformat(generated_at).date()
                if generated_at
                else date.fromisoformat(signal_date)
            )
            positions.append((move_date, _deserialize_allocation(serialized)))

    if not positions:
        return None

    latest_allocation = positions[-1][1]
    start_index = len(positions) - 1
    while start_index > 0 and positions[start_index - 1][1] == latest_allocation:
        start_index -= 1

    previous_allocation = positions[start_index - 1][1] if start_index > 0 else None
    return LastModelPosition(
        allocation=latest_allocation,
        since=positions[start_index][0],
        previous_allocation=previous_allocation,
    )


def append_weekly_signal_history(
    path: str | Path,
    result: SignalResult,
    generated_at: datetime,
    data_source: str,
    min_trade_threshold: float = 0.005,
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    should_write_header = not output_path.exists() or output_path.stat().st_size == 0

    last_position = load_last_model_position(output_path)
    if last_position is None:
        decision = "initial_signal"
    else:
        deltas = allocation_deltas(
            current_allocation=last_position.allocation,
            target_allocation=result.allocation,
            min_trade_threshold=min_trade_threshold,
        )
        decision = "position_change" if needs_rebalance(deltas) else "no_position_change"

    row = {
        "generated_at": generated_at.isoformat(timespec="seconds"),
        "signal_date": result.as_of.isoformat(),
        "data_source": data_source,
        "data_age_days": (generated_at.date() - result.as_of).days,
        "decision": decision,
        "regime": result.regime,
        "conviction": result.conviction,
        # Kept empty for compatibility with existing history files. Live portfolio
        # state is no longer tracked by the weekly signal.
        "current_allocation": "",
        "target_allocation": _serialize_allocation(result.allocation),
        "proposed_allocation": _serialize_allocation(
            result.proposed_allocation or result.allocation
        ),
        "rotation_note": result.rotation_note or "",
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


def _deserialize_allocation(serialized: str) -> dict[str, float]:
    allocation: dict[str, float] = {}
    for item in serialized.split("|"):
        symbol, weight = item.split(":", maxsplit=1)
        allocation[symbol] = float(weight)
    return allocation
