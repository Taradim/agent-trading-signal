import pytest

from agent_trading_signal.portfolio import (
    allocation_deltas,
    needs_rebalance,
    validate_portfolio_symbols,
)


def test_allocation_deltas_detect_rebalance() -> None:
    deltas = allocation_deltas(
        current_allocation={"CASH": 1.0},
        target_allocation={"SMH": 1.0},
    )

    assert needs_rebalance(deltas) is True
    assert [(delta.symbol, delta.action, delta.delta) for delta in deltas] == [
        ("SMH", "buy", 1.0),
        ("CASH", "sell", -1.0),
    ]


def test_allocation_deltas_respect_trade_threshold() -> None:
    deltas = allocation_deltas(
        current_allocation={"SMH": 0.997, "CASH": 0.003},
        target_allocation={"SMH": 1.0},
        min_trade_threshold=0.005,
    )

    assert needs_rebalance(deltas) is False
    assert [delta.action for delta in deltas] == ["hold", "hold"]


def test_validate_portfolio_symbols_rejects_unknown_symbols() -> None:
    with pytest.raises(ValueError, match="Unknown portfolio symbols: ETH"):
        validate_portfolio_symbols({"ETH": 1.0}, ["BTC", "SMH"])
