from __future__ import annotations

import pandas as pd


def simple_moving_average(series: pd.Series, window: int) -> pd.Series:
    if window <= 0:
        raise ValueError("window must be positive")
    return series.rolling(window=window, min_periods=window).mean()


def exponential_moving_average(series: pd.Series, span: int) -> pd.Series:
    if span <= 0:
        raise ValueError("span must be positive")
    return series.ewm(span=span, adjust=False, min_periods=span).mean()


def percent_change(current: float, previous: float) -> float:
    if previous == 0:
        raise ValueError("previous value cannot be zero")
    return (current / previous) - 1.0
