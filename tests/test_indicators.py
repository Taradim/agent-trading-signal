import pandas as pd
import pytest

from agent_trading_signal.indicators import exponential_moving_average, simple_moving_average


def test_simple_moving_average_starts_after_window() -> None:
    result = simple_moving_average(pd.Series([1, 2, 3, 4]), 3)

    assert pd.isna(result.iloc[0])
    assert pd.isna(result.iloc[1])
    assert result.iloc[2] == pytest.approx(2.0)
    assert result.iloc[3] == pytest.approx(3.0)


def test_exponential_moving_average_waits_for_min_periods() -> None:
    result = exponential_moving_average(pd.Series([1, 2, 3, 4]), 3)

    assert pd.isna(result.iloc[0])
    assert pd.isna(result.iloc[1])
    assert result.iloc[2] > 0
    assert result.iloc[3] > result.iloc[2]
