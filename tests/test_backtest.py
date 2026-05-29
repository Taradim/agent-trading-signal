from datetime import date

import pandas as pd

from agent_trading_signal.backtest.engine import run_weekly_backtest
from agent_trading_signal.backtest.export import equity_curve_frame, trades_frame
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
