from __future__ import annotations

from itertools import combinations

import pandas as pd

from agent_trading_signal.domain import (
    AssetRank,
    PairSignal,
    PairStrength,
    SignalResult,
    TrendStatus,
)
from agent_trading_signal.indicators import (
    exponential_moving_average,
    percent_change,
    simple_moving_average,
)
from agent_trading_signal.settings import AssetConfig, SignalConfig


def evaluate_relative_strength(
    prices: pd.DataFrame,
    assets: list[AssetConfig],
    config: SignalConfig,
) -> SignalResult:
    prices = _validate_prices(prices, assets, config)
    trends = {
        asset.symbol: _trend_status(asset.symbol, prices[asset.symbol], config) for asset in assets
    }
    pairs = _pair_strengths(prices, assets, config)
    ranks = _rank_assets(assets, trends, pairs)
    warnings = _build_warnings(prices, assets, trends, config)

    if all(trend.is_downtrend for trend in trends.values()):
        return SignalResult(
            as_of=prices.index[-1].date(),
            allocation={"CASH": 1.0},
            regime="cash_defense",
            conviction="high",
            ranks=ranks,
            trends=trends,
            pairs=pairs,
            warnings=warnings,
        )

    leaders = _select_leaders(ranks, config)
    allocation = _equal_weight(leaders)
    regime, conviction = _classify_regime(ranks, leaders)

    return SignalResult(
        as_of=prices.index[-1].date(),
        allocation=allocation,
        regime=regime,
        conviction=conviction,
        ranks=ranks,
        trends=trends,
        pairs=pairs,
        warnings=warnings,
    )


def _validate_prices(
    prices: pd.DataFrame,
    assets: list[AssetConfig],
    config: SignalConfig,
) -> pd.DataFrame:
    if prices.empty:
        raise ValueError("Price frame cannot be empty")

    expected = [asset.symbol for asset in assets]
    missing = sorted(set(expected) - set(prices.columns))
    if missing:
        raise ValueError(f"Missing prices for: {', '.join(missing)}")

    prices = prices[expected].sort_index().dropna(how="any")
    if len(prices) < config.min_observations:
        raise ValueError(
            f"At least {config.min_observations} observations are required; got {len(prices)}"
        )
    if (prices <= 0).any().any():
        raise ValueError("Prices must be strictly positive")
    return prices


def _trend_status(symbol: str, series: pd.Series, config: SignalConfig) -> TrendStatus:
    ema = exponential_moving_average(series, config.ema_window)
    sma_fast = simple_moving_average(series, config.sma_fast_window)
    sma_slow = simple_moving_average(series, config.sma_slow_window)

    price = float(series.iloc[-1])
    ema35 = _last_complete(ema, f"{symbol} EMA{config.ema_window}")
    sma100 = _last_complete(sma_fast, f"{symbol} SMA{config.sma_fast_window}")
    sma200 = _last_complete(sma_slow, f"{symbol} SMA{config.sma_slow_window}")

    return TrendStatus(
        symbol=symbol,
        price=price,
        ema35=ema35,
        sma100=sma100,
        sma200=sma200,
        above_ema35=price > ema35,
        above_sma100=price > sma100,
        above_sma200=price > sma200,
    )


def _pair_strengths(
    prices: pd.DataFrame,
    assets: list[AssetConfig],
    config: SignalConfig,
) -> list[PairStrength]:
    strengths: list[PairStrength] = []
    for left, right in combinations(assets, 2):
        ratio = prices[left.symbol] / prices[right.symbol]
        strengths.append(_pair_strength(left.symbol, right.symbol, ratio, config))
    return strengths


def _pair_strength(
    left: str,
    right: str,
    ratio: pd.Series,
    config: SignalConfig,
) -> PairStrength:
    ema = exponential_moving_average(ratio, config.ema_window)
    sma_fast = simple_moving_average(ratio, config.sma_fast_window)
    sma_slow = simple_moving_average(ratio, config.sma_slow_window)

    ratio_value = float(ratio.iloc[-1])
    ema35 = _last_complete(ema, f"{left}/{right} EMA{config.ema_window}")
    sma100 = _last_complete(sma_fast, f"{left}/{right} SMA{config.sma_fast_window}")
    sma200 = _last_complete(sma_slow, f"{left}/{right} SMA{config.sma_slow_window}")

    previous_ema = ema.iloc[-1 - config.slope_lookback]
    if pd.isna(previous_ema):
        raise ValueError(f"Not enough EMA history for {left}/{right} slope")
    ema35_slope = percent_change(ema35, float(previous_ema))

    points = 0
    points += _compare_with_deadband(ratio_value, ema35, config.ratio_deadband)
    points += _compare_with_deadband(ratio_value, sma100, config.ratio_deadband)
    points += _compare_with_deadband(ratio_value, sma200, config.ratio_deadband)
    points += _sign_with_deadband(ema35_slope, config.slope_deadband)

    if points >= 2:
        signal: PairSignal = "win"
    elif points <= -2:
        signal = "loss"
    else:
        signal = "neutral"

    return PairStrength(
        left=left,
        right=right,
        ratio=ratio_value,
        ema35=ema35,
        sma100=sma100,
        sma200=sma200,
        ema35_slope=ema35_slope,
        points=points,
        signal=signal,
    )


def _rank_assets(
    assets: list[AssetConfig],
    trends: dict[str, TrendStatus],
    pairs: list[PairStrength],
) -> list[AssetRank]:
    counters = {asset.symbol: {"wins": 0, "losses": 0, "neutral": 0} for asset in assets}

    for pair in pairs:
        if pair.signal == "win":
            counters[pair.left]["wins"] += 1
            counters[pair.right]["losses"] += 1
        elif pair.signal == "loss":
            counters[pair.left]["losses"] += 1
            counters[pair.right]["wins"] += 1
        else:
            counters[pair.left]["neutral"] += 1
            counters[pair.right]["neutral"] += 1

    ranks = [
        AssetRank(
            symbol=asset.symbol,
            wins=counter["wins"],
            losses=counter["losses"],
            neutral=counter["neutral"],
            net_score=counter["wins"] - counter["losses"],
            trend=trends[asset.symbol],
        )
        for asset in assets
        for counter in [counters[asset.symbol]]
    ]
    return sorted(
        ranks,
        key=lambda rank: (rank.net_score, rank.wins, rank.trend.bullish_points),
        reverse=True,
    )


def _select_leaders(ranks: list[AssetRank], config: SignalConfig) -> list[str]:
    eligible = [rank for rank in ranks if _entry_eligible(rank, config)]
    if not eligible:
        return ["CASH"]

    best_score = eligible[0].net_score
    leaders = [
        rank.symbol for rank in eligible if best_score - rank.net_score <= config.tie_tolerance
    ]
    return leaders[: config.max_leaders]


def _entry_eligible(rank: AssetRank, config: SignalConfig) -> bool:
    if config.require_above_sma200_for_entries and not rank.trend.above_sma200:
        return False
    return rank.trend.bullish_points >= config.entry_min_bullish_points


def _equal_weight(symbols: list[str]) -> dict[str, float]:
    if not symbols:
        return {"CASH": 1.0}
    weight = 1.0 / len(symbols)
    return dict.fromkeys(symbols, weight)


def _classify_regime(ranks: list[AssetRank], leaders: list[str]) -> tuple[str, str]:
    if leaders == ["CASH"]:
        return "cash_filter", "medium"

    leader_set = set(leaders)
    leader_ranks = [rank for rank in ranks if rank.symbol in leader_set]
    best = ranks[0]
    second_score = ranks[1].net_score if len(ranks) > 1 else best.net_score
    separation = best.net_score - second_score
    total_pairs_per_asset = best.wins + best.losses + best.neutral
    neutral_ratio = best.neutral / total_pairs_per_asset if total_pairs_per_asset else 1.0

    if len(leaders) == 1 and best.wins >= max(1, total_pairs_per_asset - 1) and separation >= 2:
        return "clear_trend", "high"
    if neutral_ratio >= 0.5 or len(leaders) >= 3:
        return "range", "low"
    if all(rank.trend.bullish_points >= 2 for rank in leader_ranks):
        return "transition", "medium"
    return "transition", "low"


def _build_warnings(
    prices: pd.DataFrame,
    assets: list[AssetConfig],
    trends: dict[str, TrendStatus],
    config: SignalConfig,
) -> list[str]:
    warnings: list[str] = []
    if len(prices) < config.sma_slow_window + 20:
        warnings.append("Short history: SMA200 signals exist, but backtests will be fragile.")
    bearish_assets = [asset.symbol for asset in assets if trends[asset.symbol].is_downtrend]
    if bearish_assets and len(bearish_assets) < len(assets):
        warnings.append("Some assets are in absolute downtrend: " + ", ".join(bearish_assets))
    if config.require_above_sma200_for_entries:
        rejected = [asset.symbol for asset in assets if not trends[asset.symbol].above_sma200]
        if rejected and len(rejected) < len(assets):
            warnings.append("SMA200 entry filter rejects: " + ", ".join(rejected))
    if config.entry_min_bullish_points > 1:
        rejected = [
            asset.symbol
            for asset in assets
            if trends[asset.symbol].bullish_points < config.entry_min_bullish_points
        ]
        if rejected and len(rejected) < len(assets):
            warnings.append(
                f"Absolute trend entry filter rejects assets below "
                f"{config.entry_min_bullish_points}/3 trend points: " + ", ".join(rejected)
            )
    return warnings


def _last_complete(series: pd.Series, label: str) -> float:
    value = series.iloc[-1]
    if pd.isna(value):
        raise ValueError(f"Missing complete value for {label}")
    return float(value)


def _compare_with_deadband(current: float, reference: float, deadband: float) -> int:
    return _sign_with_deadband(percent_change(current, reference), deadband)


def _sign_with_deadband(value: float, deadband: float) -> int:
    if value > deadband:
        return 1
    if value < -deadband:
        return -1
    return 0
