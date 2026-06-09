from datetime import date, datetime

from agent_trading_signal.domain import AssetRank, PairStrength, SignalResult, TrendStatus
from agent_trading_signal.reporting.markdown import (
    render_weekly_decision_report,
    render_weekly_notification,
)


def test_weekly_decision_report_shows_trade_plan() -> None:
    report = render_weekly_decision_report(
        result=_signal_result(),
        current_allocation={"CASH": 1.0},
        generated_at=datetime(2026, 5, 31, 9, 0),
        data_source="test prices",
    )

    assert "**Decision:** rebalance required" in report
    assert "| SMH | 0.00% | 100.00% | +100.00% | buy |" in report
    assert "| CASH | 100.00% | 0.00% | -100.00% | sell |" in report
    assert "SMA200 entry filter rejects: BTC" in report


def test_weekly_notification_is_short_and_actionable() -> None:
    notification = render_weekly_notification(
        result=_signal_result(),
        current_allocation={"CASH": 1.0},
        generated_at=datetime(2026, 5, 31, 9, 0),
    )

    assert "Weekly Trading Signal - 2026-05-29" in notification
    assert "Decision: rebalance required" in notification
    assert "Target: SMH 100.00%" in notification
    assert "Trade plan: BUY SMH +100.00%; SELL CASH -100.00%" in notification
    assert "SMA200 entry filter rejects: BTC" in notification


def _signal_result() -> SignalResult:
    return SignalResult(
        as_of=date(2026, 5, 29),
        allocation={"SMH": 1.0},
        regime="clear_trend",
        conviction="high",
        ranks=[
            AssetRank(
                symbol="SMH",
                wins=1,
                losses=0,
                neutral=0,
                net_score=1,
                trend=_trend("SMH"),
            ),
            AssetRank(
                symbol="BTC",
                wins=0,
                losses=1,
                neutral=0,
                net_score=-1,
                trend=_trend("BTC"),
            ),
        ],
        trends={"SMH": _trend("SMH"), "BTC": _trend("BTC")},
        pairs=[
            PairStrength(
                left="SMH",
                right="BTC",
                ratio=1.2,
                ema35=1.1,
                sma100=1.0,
                sma200=0.9,
                ema35_slope=0.02,
                points=4,
                signal="win",
            )
        ],
        warnings=["SMA200 entry filter rejects: BTC"],
    )


def _trend(symbol: str) -> TrendStatus:
    return TrendStatus(
        symbol=symbol,
        price=100.0,
        ema35=90.0,
        sma100=80.0,
        sma200=70.0,
        above_ema35=True,
        above_sma100=True,
        above_sma200=True,
    )
