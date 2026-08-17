from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

import pandas as pd

PairSignal = Literal["win", "loss", "neutral"]
Regime = Literal[
    "cash_defense",
    "cash_filter",
    "clear_trend",
    "transition",
    "range",
]
Conviction = Literal["high", "medium", "low"]


@dataclass(frozen=True)
class TrendStatus:
    symbol: str
    price: float
    ema35: float
    sma100: float
    sma200: float
    above_ema35: bool
    above_sma100: bool
    above_sma200: bool

    @property
    def bullish_points(self) -> int:
        return int(self.above_ema35) + int(self.above_sma100) + int(self.above_sma200)

    @property
    def is_downtrend(self) -> bool:
        return not self.above_ema35 and not self.above_sma100 and not self.above_sma200

    @property
    def label(self) -> str:
        if self.bullish_points == 3:
            return "bullish"
        if self.bullish_points == 0:
            return "bearish"
        return "mixed"


@dataclass(frozen=True)
class PairStrength:
    left: str
    right: str
    ratio: float
    ema35: float
    sma100: float
    sma200: float
    ema35_slope: float
    points: int
    signal: PairSignal


@dataclass(frozen=True)
class AssetRank:
    symbol: str
    wins: int
    losses: int
    neutral: int
    net_score: int
    trend: TrendStatus


@dataclass(frozen=True)
class SignalResult:
    as_of: date
    allocation: dict[str, float]
    regime: Regime
    conviction: Conviction
    ranks: list[AssetRank]
    trends: dict[str, TrendStatus]
    pairs: list[PairStrength]
    warnings: list[str]
    proposed_allocation: dict[str, float] | None = None
    rotation_note: str | None = None

    @property
    def leaders(self) -> list[str]:
        return [
            symbol for symbol, weight in self.allocation.items() if symbol != "CASH" and weight > 0
        ]


@dataclass(frozen=True)
class Trade:
    signal_date: date
    execution_date: date
    allocation: dict[str, float]
    turnover: float
    cost: float
    capital_after_cost: float
    regime: Regime
    conviction: Conviction


@dataclass(frozen=True)
class BacktestMetrics:
    total_return: float
    cagr: float
    max_drawdown: float
    volatility: float
    trade_count: int
    average_turnover: float
    time_in_cash: float


@dataclass(frozen=True)
class BacktestResult:
    equity_curve: pd.Series
    trades: list[Trade]
    metrics: BacktestMetrics
    benchmark_curves: dict[str, pd.Series]
