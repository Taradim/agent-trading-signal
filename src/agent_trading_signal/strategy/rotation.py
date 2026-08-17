from __future__ import annotations

from dataclasses import replace
from datetime import date

from agent_trading_signal.domain import PairStrength, SignalResult
from agent_trading_signal.settings import SignalConfig


def apply_rotation_policy(
    signal: SignalResult,
    incumbent_allocation: dict[str, float] | None,
    incumbent_since: date | None,
    evaluation_date: date,
    signal_config: SignalConfig,
    min_holding_days: int,
) -> SignalResult:
    proposed = signal.allocation
    if incumbent_allocation is None:
        return replace(
            signal,
            proposed_allocation=proposed,
            rotation_note="Initial model position accepted.",
        )
    if _allocations_equal(incumbent_allocation, proposed):
        return replace(
            signal,
            proposed_allocation=proposed,
            rotation_note="The raw signal is unchanged from the last model position.",
        )
    if proposed == {"CASH": 1.0}:
        return replace(
            signal,
            proposed_allocation=proposed,
            rotation_note="Rotation to CASH accepted immediately.",
        )
    if incumbent_allocation == {"CASH": 1.0}:
        return replace(
            signal,
            proposed_allocation=proposed,
            rotation_note="Entry from CASH accepted.",
        )
    if not _position_is_eligible(incumbent_allocation, signal, signal_config):
        return replace(
            signal,
            proposed_allocation=proposed,
            rotation_note="Rotation accepted because the last position is no longer eligible.",
        )

    direct_confirmation = _direct_confirmation(
        incumbent_allocation,
        proposed,
        signal.pairs,
    )
    if direct_confirmation is not None:
        return replace(
            signal,
            allocation=incumbent_allocation,
            proposed_allocation=proposed,
            rotation_note=(
                f"Rotation blocked: {direct_confirmation}. "
                f"Keeping {_format_allocation(incumbent_allocation)}."
            ),
        )

    days_held = (
        (evaluation_date - incumbent_since).days
        if incumbent_since is not None
        else min_holding_days
    )
    if days_held < min_holding_days and signal.conviction != "high":
        return replace(
            signal,
            allocation=incumbent_allocation,
            proposed_allocation=proposed,
            rotation_note=(
                f"Rotation blocked after {max(days_held, 0)} days: the minimum holding period "
                f"is {min_holding_days} days for {signal.conviction}-conviction signals. "
                f"Keeping {_format_allocation(incumbent_allocation)}."
            ),
        )

    return replace(
        signal,
        proposed_allocation=proposed,
        rotation_note="Rotation accepted after direct relative-strength confirmation.",
    )


def _position_is_eligible(
    allocation: dict[str, float],
    signal: SignalResult,
    config: SignalConfig,
) -> bool:
    symbols = [symbol for symbol, weight in allocation.items() if symbol != "CASH" and weight > 0]
    if not symbols:
        return False
    for symbol in symbols:
        trend = signal.trends.get(symbol)
        if trend is None:
            return False
        if config.require_above_sma200_for_entries and not trend.above_sma200:
            return False
        if trend.bullish_points < config.entry_min_bullish_points:
            return False
    return True


def _direct_confirmation(
    incumbent: dict[str, float],
    proposed: dict[str, float],
    pairs: list[PairStrength],
) -> str | None:
    incumbents = _active_symbols(incumbent)
    challengers = [symbol for symbol in _active_symbols(proposed) if symbol not in incumbents]
    replaced = [symbol for symbol in incumbents if symbol not in _active_symbols(proposed)]
    if not challengers or not replaced:
        return "the proposed allocation has no directly confirmed challenger"

    for challenger in challengers:
        for current in replaced:
            pair = _find_pair(challenger, current, pairs)
            if pair is None or not _symbol_wins_pair(challenger, pair):
                pair_label = (
                    f"{pair.left}/{pair.right}" if pair is not None else f"{challenger}/{current}"
                )
                pair_signal = pair.signal if pair is not None else "missing"
                return (
                    f"{challenger} does not beat {current} directly ({pair_label}: {pair_signal})"
                )
    return None


def _active_symbols(allocation: dict[str, float]) -> list[str]:
    return [symbol for symbol, weight in allocation.items() if symbol != "CASH" and weight > 0]


def _find_pair(left: str, right: str, pairs: list[PairStrength]) -> PairStrength | None:
    return next(
        (pair for pair in pairs if {pair.left, pair.right} == {left, right}),
        None,
    )


def _symbol_wins_pair(symbol: str, pair: PairStrength) -> bool:
    return (pair.left == symbol and pair.signal == "win") or (
        pair.right == symbol and pair.signal == "loss"
    )


def _allocations_equal(left: dict[str, float], right: dict[str, float]) -> bool:
    symbols = set(left) | set(right)
    return all(abs(left.get(symbol, 0.0) - right.get(symbol, 0.0)) < 1e-9 for symbol in symbols)


def _format_allocation(allocation: dict[str, float]) -> str:
    return ", ".join(f"{symbol} {weight:.0%}" for symbol, weight in allocation.items())
