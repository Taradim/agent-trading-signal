from datetime import date

import pandas as pd

from agent_trading_signal.settings import AssetConfig, SignalConfig
from agent_trading_signal.strategy.relative_strength import evaluate_relative_strength

ASSETS = [
    AssetConfig(symbol="A", name="Asset A", asset_class="test", price_symbol="A", trade_symbol="A"),
    AssetConfig(symbol="B", name="Asset B", asset_class="test", price_symbol="B", trade_symbol="B"),
    AssetConfig(symbol="C", name="Asset C", asset_class="test", price_symbol="C", trade_symbol="C"),
]
CONFIG = SignalConfig()


def dates(length: int) -> pd.DatetimeIndex:
    start = date(2025, 1, 1)
    return pd.date_range(start=start, periods=length, freq="D")


def compound(start: float, daily_return: float, length: int) -> list[float]:
    return [start * ((1.0 + daily_return) ** index) for index in range(length)]


def price_frame(data: dict[str, list[float]]) -> pd.DataFrame:
    return pd.DataFrame(data, index=dates(len(next(iter(data.values())))))


def test_cash_when_all_assets_are_below_absolute_trend_filters() -> None:
    length = 260
    prices = price_frame(
        {
            "A": compound(300, -0.004, length),
            "B": compound(200, -0.003, length),
            "C": compound(100, -0.002, length),
        }
    )

    result = evaluate_relative_strength(prices, ASSETS, CONFIG)

    assert result.allocation == {"CASH": 1.0}
    assert result.regime == "cash_defense"


def test_single_leader_gets_full_allocation() -> None:
    length = 260
    prices = price_frame(
        {
            "A": compound(100, 0.004, length),
            "B": compound(100, 0.001, length),
            "C": compound(100, -0.001, length),
        }
    )

    result = evaluate_relative_strength(prices, ASSETS, CONFIG)

    assert result.allocation == {"A": 1.0}
    assert result.leaders == ["A"]


def test_equivalent_leaders_are_equal_weighted() -> None:
    length = 260
    prices = price_frame(
        {
            "A": compound(100, 0.003, length),
            "B": compound(100, 0.003, length),
            "C": compound(100, -0.001, length),
        }
    )

    result = evaluate_relative_strength(prices, ASSETS, CONFIG)

    assert result.allocation == {"A": 0.5, "B": 0.5}
