from __future__ import annotations

from datetime import date

import pandas as pd
import yfinance as yf

from agent_trading_signal.data.csv_prices import clean_price_frame
from agent_trading_signal.settings import AssetConfig


def download_adjusted_closes(
    assets: list[AssetConfig],
    start: date | str,
    end: date | str | None = None,
) -> pd.DataFrame:
    tickers = [asset.price_symbol for asset in assets]
    raw = yf.download(
        tickers=tickers,
        start=start,
        end=end,
        interval="1d",
        auto_adjust=True,
        progress=False,
        group_by="column",
        threads=True,
    )
    close = _extract_close_frame(raw, tickers)
    rename_map = {asset.price_symbol: asset.symbol for asset in assets}
    close = close.rename(columns=rename_map)
    close = close[[asset.symbol for asset in assets]]
    close.index = pd.to_datetime(close.index).tz_localize(None)
    return clean_price_frame(close)


def _extract_close_frame(raw: pd.DataFrame, tickers: list[str]) -> pd.DataFrame:
    if raw.empty:
        raise ValueError("yfinance returned no data")

    if isinstance(raw.columns, pd.MultiIndex):
        first_level = raw.columns.get_level_values(0)
        if "Close" in first_level:
            close = raw["Close"]
        elif "Adj Close" in first_level:
            close = raw["Adj Close"]
        else:
            raise ValueError("yfinance response does not contain Close prices")
    else:
        if "Close" not in raw.columns:
            raise ValueError("yfinance response does not contain a Close column")
        close = raw[["Close"]].copy()
        close.columns = tickers

    missing = sorted(set(tickers) - set(close.columns))
    if missing:
        raise ValueError(f"Missing yfinance data for: {', '.join(missing)}")
    return close
