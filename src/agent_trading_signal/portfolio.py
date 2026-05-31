from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

AllocationAction = Literal["buy", "sell", "hold"]


@dataclass(frozen=True)
class AllocationDelta:
    symbol: str
    current_weight: float
    target_weight: float
    delta: float
    action: AllocationAction


def allocation_deltas(
    current_allocation: dict[str, float],
    target_allocation: dict[str, float],
    min_trade_threshold: float = 0.005,
) -> list[AllocationDelta]:
    if min_trade_threshold < 0:
        raise ValueError("min_trade_threshold must be non-negative")

    symbols = _ordered_symbols(current_allocation, target_allocation)
    deltas: list[AllocationDelta] = []
    for symbol in symbols:
        current_weight = current_allocation.get(symbol, 0.0)
        target_weight = target_allocation.get(symbol, 0.0)
        delta = target_weight - current_weight
        if abs(delta) < min_trade_threshold:
            action: AllocationAction = "hold"
        elif delta > 0:
            action = "buy"
        else:
            action = "sell"
        deltas.append(
            AllocationDelta(
                symbol=symbol,
                current_weight=current_weight,
                target_weight=target_weight,
                delta=delta,
                action=action,
            )
        )
    return deltas


def needs_rebalance(deltas: list[AllocationDelta]) -> bool:
    return any(delta.action != "hold" for delta in deltas)


def validate_portfolio_symbols(
    allocation: dict[str, float],
    allowed_symbols: list[str],
) -> None:
    allowed = {*allowed_symbols, "CASH"}
    unknown = sorted(set(allocation) - allowed)
    if unknown:
        raise ValueError(f"Unknown portfolio symbols: {', '.join(unknown)}")


def _ordered_symbols(
    current_allocation: dict[str, float],
    target_allocation: dict[str, float],
) -> list[str]:
    symbols: list[str] = []
    for symbol in [*target_allocation, *current_allocation]:
        if symbol not in symbols and symbol != "CASH":
            symbols.append(symbol)
    if "CASH" in current_allocation or "CASH" in target_allocation:
        symbols.append("CASH")
    return symbols
