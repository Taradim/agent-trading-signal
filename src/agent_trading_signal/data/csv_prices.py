from __future__ import annotations

from pathlib import Path

import pandas as pd

from agent_trading_signal.settings import AssetConfig


def load_price_csv(path: str | Path, assets: list[AssetConfig]) -> pd.DataFrame:
    frame = pd.read_csv(path, parse_dates=["Date"])
    if "Date" not in frame.columns:
        raise ValueError("CSV file must contain a Date column")

    column_map = _resolve_columns(frame.columns, assets)
    prices = frame[["Date", *column_map.values()]].rename(
        columns={column: symbol for symbol, column in column_map.items()}
    )
    prices = prices.set_index("Date").sort_index()
    prices.index = pd.to_datetime(prices.index).tz_localize(None)
    prices = prices.apply(pd.to_numeric, errors="raise")
    return clean_price_frame(prices)


def save_price_csv(prices: pd.DataFrame, path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    prices.reset_index(names="Date").to_csv(output_path, index=False)


def clean_price_frame(prices: pd.DataFrame, forward_fill: bool = False) -> pd.DataFrame:
    """Normalize prices and align them to rows where all assets have valid closes.

    By default, missing rows are dropped instead of forward-filled. This matters for
    mixed crypto/ETF universes: crypto trades 7 days a week, while ETFs do not. A
    common close calendar keeps the backtest from executing ETF trades on weekends
    or market holidays using stale prices.
    """
    if prices.empty:
        raise ValueError("Price frame cannot be empty")
    prices = prices.sort_index()
    prices = prices[~prices.index.duplicated(keep="last")]
    if forward_fill:
        prices = prices.ffill()
    prices = prices.dropna(how="any")
    if (prices <= 0).any().any():
        raise ValueError("Prices must be strictly positive")
    return prices


def _resolve_columns(columns: pd.Index, assets: list[AssetConfig]) -> dict[str, str]:
    available = set(columns)
    column_map: dict[str, str] = {}
    for asset in assets:
        if asset.price_symbol in available:
            column_map[asset.symbol] = asset.price_symbol
        elif asset.symbol in available:
            column_map[asset.symbol] = asset.symbol
        else:
            raise ValueError(
                f"CSV file must contain a column for {asset.symbol} or {asset.price_symbol}"
            )
    return column_map
