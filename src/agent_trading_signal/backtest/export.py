from __future__ import annotations

from pathlib import Path

import pandas as pd

from agent_trading_signal.domain import BacktestResult, Trade


def equity_curve_frame(result: BacktestResult) -> pd.DataFrame:
    frame = result.equity_curve.to_frame(name="strategy")
    for symbol, curve in result.benchmark_curves.items():
        frame[symbol] = curve
    return frame.reset_index(names="Date")


def trades_frame(result_or_trades: BacktestResult | list[Trade]) -> pd.DataFrame:
    if isinstance(result_or_trades, BacktestResult):
        return _trades_with_realized_pnl_frame(result_or_trades)

    trades = result_or_trades
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


def write_trades(result_or_trades: BacktestResult | list[Trade], path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    trades_frame(result_or_trades).to_csv(output_path, index=False)


def _format_allocation(allocation: dict[str, float]) -> str:
    return ";".join(f"{symbol}:{weight:.6f}" for symbol, weight in allocation.items())


def _trades_with_realized_pnl_frame(result: BacktestResult) -> pd.DataFrame:
    rows = []
    for index, trade in enumerate(result.trades):
        entry_capital = trade.capital_after_cost
        if index + 1 < len(result.trades):
            next_trade = result.trades[index + 1]
            exit_date = next_trade.execution_date
            exit_capital_before_next_cost = next_trade.capital_after_cost + next_trade.cost
            exit_reason = "next_trade"
        else:
            exit_date = result.equity_curve.index[-1].date()
            exit_capital_before_next_cost = float(result.equity_curve.iloc[-1])
            exit_reason = "end_of_data"

        pnl = exit_capital_before_next_cost - entry_capital
        realized_return = pnl / entry_capital if entry_capital else 0.0
        rows.append(
            {
                "signal_date": trade.signal_date,
                "execution_date": trade.execution_date,
                "exit_date": exit_date,
                "holding_days": (exit_date - trade.execution_date).days,
                "allocation": _format_allocation(trade.allocation),
                "turnover": trade.turnover,
                "entry_cost": trade.cost,
                "entry_capital": entry_capital,
                "exit_capital_before_next_cost": exit_capital_before_next_cost,
                "pnl": pnl,
                "return": realized_return,
                "outcome_band": _outcome_band(realized_return),
                "regime": trade.regime,
                "conviction": trade.conviction,
                "exit_reason": exit_reason,
            }
        )
    return pd.DataFrame(rows)


def _outcome_band(realized_return: float) -> str:
    if realized_return < -0.10:
        return "loss_below_-10%"
    if realized_return > 0.10:
        return "gain_above_+10%"
    return "between_-10%_and_+10%"
