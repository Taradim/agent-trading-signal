from __future__ import annotations

from pathlib import Path

import pandas as pd

from agent_trading_signal.domain import BacktestResult, Trade


def equity_curve_frame(result: BacktestResult) -> pd.DataFrame:
    frame = result.equity_curve.to_frame(name="strategy")
    for symbol, curve in result.benchmark_curves.items():
        frame[symbol] = curve
    return frame.reset_index(names="Date")


def trades_frame(trades: list[Trade]) -> pd.DataFrame:
    rows = [
        {
            "signal_date": trade.signal_date,
            "execution_date": trade.execution_date,
            "allocation": _format_allocation(trade.allocation),
            "turnover": trade.turnover,
            "cost": trade.cost,
            "capital_after_cost": trade.capital_after_cost,
            "regime": trade.regime,
            "conviction": trade.conviction,
        }
        for trade in trades
    ]
    return pd.DataFrame(rows)


def write_equity_curve(result: BacktestResult, path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    equity_curve_frame(result).to_csv(output_path, index=False)


def write_trades(trades: list[Trade], path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    trades_frame(trades).to_csv(output_path, index=False)


def _format_allocation(allocation: dict[str, float]) -> str:
    return ";".join(f"{symbol}:{weight:.6f}" for symbol, weight in allocation.items())
