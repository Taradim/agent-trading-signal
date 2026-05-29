from __future__ import annotations

import tomllib
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AssetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(min_length=1)
    name: str = Field(min_length=1)
    asset_class: str = Field(min_length=1)
    price_symbol: str = Field(min_length=1)
    trade_symbol: str = Field(min_length=1)

    @field_validator("symbol", "price_symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()


class UniverseConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assets: list[AssetConfig] = Field(min_length=2)

    @model_validator(mode="after")
    def validate_unique_symbols(self) -> UniverseConfig:
        symbols = [asset.symbol for asset in self.assets]
        duplicates = sorted({symbol for symbol in symbols if symbols.count(symbol) > 1})
        if duplicates:
            raise ValueError(f"Duplicate asset symbols: {', '.join(duplicates)}")
        return self

    @property
    def symbols(self) -> list[str]:
        return [asset.symbol for asset in self.assets]

    def active_assets(self, excluded_symbols: list[str] | None = None) -> list[AssetConfig]:
        excluded = {symbol.strip().upper() for symbol in excluded_symbols or []}
        unknown = excluded - set(self.symbols)
        if unknown:
            raise ValueError(f"Unknown excluded symbols: {', '.join(sorted(unknown))}")

        assets = [asset for asset in self.assets if asset.symbol not in excluded]
        if len(assets) < 2:
            raise ValueError("At least two active assets are required")
        return assets


class SignalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ema_window: int = Field(default=35, ge=2)
    sma_fast_window: int = Field(default=100, ge=2)
    sma_slow_window: int = Field(default=200, ge=2)
    slope_lookback: int = Field(default=10, ge=1)
    ratio_deadband: float = Field(default=0.001, ge=0)
    slope_deadband: float = Field(default=0.0005, ge=0)
    tie_tolerance: int = Field(default=1, ge=0)
    max_leaders: int = Field(default=4, ge=1)
    require_above_sma200_for_entries: bool = True
    entry_min_bullish_points: int = Field(default=1, ge=1, le=3)

    @model_validator(mode="after")
    def validate_windows(self) -> SignalConfig:
        if self.sma_fast_window >= self.sma_slow_window:
            raise ValueError("sma_fast_window must be lower than sma_slow_window")
        return self

    @property
    def min_observations(self) -> int:
        return max(self.sma_slow_window, self.ema_window + self.slope_lookback)


class BacktestConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: date = date(2020, 1, 1)
    initial_capital: float = Field(default=10000.0, gt=0)
    decision_frequency: str = "W-FRI"
    execution_lag_business_days: int = Field(default=1, ge=0)
    transaction_cost_bps: float = Field(default=5.0, ge=0)
    slippage_bps: float = Field(default=5.0, ge=0)
    min_holding_days: int = Field(default=28, ge=0)
    lookback_buffer_days: int = Field(default=500, ge=0)
    benchmarks: list[str] = Field(default_factory=lambda: ["SPY", "QQQ", "SMH", "BTC"])


class StrategyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal: SignalConfig = Field(default_factory=SignalConfig)
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)


def load_universe(path: str | Path) -> UniverseConfig:
    return UniverseConfig.model_validate(_load_toml(path))


def load_strategy_config(path: str | Path) -> StrategyConfig:
    return StrategyConfig.model_validate(_load_toml(path))


def _load_toml(path: str | Path) -> dict:
    with Path(path).open("rb") as file:
        return tomllib.load(file)
