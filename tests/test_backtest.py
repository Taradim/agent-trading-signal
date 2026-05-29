from datetime import date

import pandas as pd

from agent_trading_signal.backtest.engine import _apply_flip_flop_stabilizer, run_weekly_backtest
from agent_trading_signal.backtest.export import equity_curve_frame, trades_frame
from agent_trading_signal.domain import AssetRank, PairStrength, SignalResult, TrendStatus
from agent_trading_signal.settings import AssetConfig, BacktestConfig, SignalConfig

ASSETS = [
    AssetConfig(symbol="A", name="Asset A", asset_class="test", price_symbol="A", trade_symbol="A"),
    AssetConfig(symbol="B", name="Asset B", asset_class="test", price_symbol="B", trade_symbol="B"),
    AssetConfig(symbol="C", name="Asset C", asset_class="test", price_symbol="C", trade_symbol="C"),
]


def test_backtest_produces_equity_curve_and_trades() -> None:
    length = 520
    index = pd.date_range(start="2019-01-01", periods=length, freq="D")
    prices = pd.DataFrame(
        {
            "A": [100 * (1.003**i) for i in range(length)],
            "B": [100 * (1.001**i) for i in range(length)],
            "C": [100 * (0.999**i) for i in range(length)],
        },
        index=index,
    )

    result = run_weekly_backtest(
        prices=prices,
        assets=ASSETS,
        signal_config=SignalConfig(),
        backtest_config=BacktestConfig(start=date(2020, 1, 1), benchmarks=["A"]),
    )

    assert not result.equity_curve.empty
    assert result.metrics.trade_count >= 1
    assert "A" in result.benchmark_curves
    assert list(equity_curve_frame(result).columns) == ["Date", "strategy", "A"]
    assert "allocation" in trades_frame(result.trades).columns
    assert "pnl" in trades_frame(result).columns
    assert "outcome_band" in trades_frame(result).columns


def test_flip_flop_stabilizer_blends_repeated_two_asset_switches() -> None:
    config = SignalConfig(
        use_flip_flop_stabilizer=True,
        flip_flop_lookback_signals=4,
        flip_flop_min_switches=3,
        flip_flop_tie_tolerance_boost=1,
    )
    scheduled = [
        (pd.Timestamp("2025-01-06"), _signal("A", {"A": 4, "B": 3, "C": -2})),
        (pd.Timestamp("2025-01-13"), _signal("B", {"A": 3, "B": 4, "C": -2})),
        (pd.Timestamp("2025-01-20"), _signal("A", {"A": 4, "B": 3, "C": -2})),
        (pd.Timestamp("2025-01-27"), _signal("B", {"A": 3, "B": 4, "C": -2})),
        (pd.Timestamp("2025-02-03"), _signal("A", {"A": 4, "B": 3, "C": -2})),
    ]

    stabilized = _apply_flip_flop_stabilizer(scheduled, config)

    assert stabilized[-2][1].allocation == {"B": 0.5, "A": 0.5}
    assert stabilized[-2][1].regime == "stabilized_range"
    assert stabilized[-2][1].conviction == "medium"
    assert stabilized[-1][1].allocation == {"A": 0.5, "B": 0.5}
    assert stabilized[-1][1].regime == "stabilized_range"


def _signal(leader: str, scores: dict[str, int]) -> SignalResult:
    ranks = [
        AssetRank(
            symbol=symbol,
            wins=max(score, 0),
            losses=max(-score, 0),
            neutral=0,
            net_score=score,
            trend=TrendStatus(
                symbol=symbol,
                price=100.0,
                ema35=90.0,
                sma100=85.0,
                sma200=80.0,
                above_ema35=True,
                above_sma100=True,
                above_sma200=True,
            ),
        )
        for symbol, score in scores.items()
    ]
    ranks = sorted(ranks, key=lambda rank: rank.net_score, reverse=True)
    return SignalResult(
        as_of=date(2025, 1, 3),
        allocation={leader: 1.0},
        regime="clear_trend",
        conviction="high",
        ranks=ranks,
        trends={rank.symbol: rank.trend for rank in ranks},
        pairs=[
            PairStrength(
                left="A",
                right="B",
                ratio=1.0,
                ema35=1.0,
                sma100=1.0,
                sma200=1.0,
                ema35_slope=0.0,
                points=0,
                signal="neutral",
            )
        ],
        warnings=[],
    )
