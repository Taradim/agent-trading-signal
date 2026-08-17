from datetime import date

from agent_trading_signal.domain import AssetRank, PairStrength, SignalResult, TrendStatus
from agent_trading_signal.settings import SignalConfig
from agent_trading_signal.strategy.rotation import apply_rotation_policy

CONFIG = SignalConfig(entry_min_bullish_points=3)


def test_neutral_direct_ratio_keeps_eligible_incumbent() -> None:
    decision = _apply(_signal(pair_signal="neutral"), days_held=60)

    assert decision.allocation == {"SMH": 1.0}
    assert decision.proposed_allocation == {"SPY": 1.0}
    assert "SPY does not beat SMH directly" in (decision.rotation_note or "")


def test_direct_win_rotates_after_minimum_holding_period() -> None:
    decision = _apply(_signal(pair_signal="loss"), days_held=60)

    assert decision.allocation == {"SPY": 1.0}
    assert "direct relative-strength confirmation" in (decision.rotation_note or "")


def test_medium_conviction_direct_win_waits_for_minimum_holding_period() -> None:
    decision = _apply(_signal(pair_signal="loss"), days_held=14)

    assert decision.allocation == {"SMH": 1.0}
    assert "minimum holding period is 28 days" in (decision.rotation_note or "")


def test_high_conviction_direct_win_can_rotate_early() -> None:
    signal = _signal(pair_signal="loss")
    signal = SignalResult(**{**signal.__dict__, "conviction": "high"})

    decision = _apply(signal, days_held=14)

    assert decision.allocation == {"SPY": 1.0}


def test_ineligible_incumbent_can_be_replaced_without_direct_win() -> None:
    signal = _signal(pair_signal="neutral", incumbent_bullish=False)

    decision = _apply(signal, days_held=14)

    assert decision.allocation == {"SPY": 1.0}
    assert "no longer eligible" in (decision.rotation_note or "")


def _apply(signal: SignalResult, days_held: int) -> SignalResult:
    evaluation_date = date(2026, 8, 17)
    return apply_rotation_policy(
        signal=signal,
        incumbent_allocation={"SMH": 1.0},
        incumbent_since=date.fromordinal(evaluation_date.toordinal() - days_held),
        evaluation_date=evaluation_date,
        signal_config=CONFIG,
        min_holding_days=28,
    )


def _signal(pair_signal: str, incumbent_bullish: bool = True) -> SignalResult:
    smh_trend = _trend("SMH", bullish=incumbent_bullish)
    spy_trend = _trend("SPY", bullish=True)
    return SignalResult(
        as_of=date(2026, 8, 14),
        allocation={"SPY": 1.0},
        regime="transition",
        conviction="medium",
        ranks=[
            AssetRank(
                symbol="SPY",
                wins=1,
                losses=0,
                neutral=0,
                net_score=1,
                trend=spy_trend,
            ),
            AssetRank(
                symbol="SMH",
                wins=0,
                losses=1,
                neutral=0,
                net_score=-1,
                trend=smh_trend,
            ),
        ],
        trends={"SMH": smh_trend, "SPY": spy_trend},
        pairs=[
            PairStrength(
                left="SMH",
                right="SPY",
                ratio=0.75,
                ema35=0.76,
                sma100=0.74,
                sma200=0.65,
                ema35_slope=-0.01,
                points=0 if pair_signal == "neutral" else -4,
                signal=pair_signal,  # type: ignore[arg-type]
            )
        ],
        warnings=[],
    )


def _trend(symbol: str, bullish: bool) -> TrendStatus:
    return TrendStatus(
        symbol=symbol,
        price=100.0,
        ema35=90.0 if bullish else 110.0,
        sma100=80.0 if bullish else 120.0,
        sma200=70.0 if bullish else 130.0,
        above_ema35=bullish,
        above_sma100=bullish,
        above_sma200=bullish,
    )
