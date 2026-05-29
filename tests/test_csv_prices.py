import pandas as pd

from agent_trading_signal.data.csv_prices import clean_price_frame


def test_clean_price_frame_drops_missing_rows_by_default() -> None:
    prices = pd.DataFrame(
        {
            "A": [1.0, None, 3.0],
            "B": [1.0, 2.0, 3.0],
        },
        index=pd.date_range("2026-01-01", periods=3),
    )

    result = clean_price_frame(prices)

    assert list(result.index) == [pd.Timestamp("2026-01-01"), pd.Timestamp("2026-01-03")]


def test_clean_price_frame_can_forward_fill_when_requested() -> None:
    prices = pd.DataFrame(
        {
            "A": [1.0, None, 3.0],
            "B": [1.0, 2.0, 3.0],
        },
        index=pd.date_range("2026-01-01", periods=3),
    )

    result = clean_price_frame(prices, forward_fill=True)

    assert len(result) == 3
    assert result.loc[pd.Timestamp("2026-01-02"), "A"] == 1.0
