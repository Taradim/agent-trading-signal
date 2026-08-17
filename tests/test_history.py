from datetime import date, datetime

import pandas as pd

from agent_trading_signal.domain import AssetRank, PairStrength, SignalResult, TrendStatus
from agent_trading_signal.reporting.history import (
    append_weekly_signal_history,
    load_last_model_position,
)


def test_append_weekly_signal_history_writes_csv_rows(tmp_path) -> None:
    path = tmp_path / "weekly_signals.csv"
    result = _signal_result()

    append_weekly_signal_history(
        path=path,
        result=result,
        generated_at=datetime(2026, 6, 9, 22, 0),
        data_source="test prices",
    )
    append_weekly_signal_history(
        path=path,
        result=result,
        generated_at=datetime(2026, 6, 9, 22, 1),
        data_source="test prices",
    )

    rows = pd.read_csv(path)

    assert list(rows["decision"]) == ["initial_signal", "no_position_change"]
    assert list(rows["target_allocation"]) == ["SMH:1.000000", "SMH:1.000000"]
    assert rows["current_allocation"].isna().all()
    assert rows.loc[0, "leaders"] == "SMH"
    assert rows.loc[0, "top_rank"] == "SMH"

    last_position = load_last_model_position(path)
    assert last_position is not None
    assert last_position.allocation == {"SMH": 1.0}
    assert last_position.since == date(2026, 6, 9)
    assert last_position.previous_allocation is None


def _signal_result() -> SignalResult:
    trend = TrendStatus(
        symbol="SMH",
        price=100.0,
        ema35=90.0,
        sma100=80.0,
        sma200=70.0,
        above_ema35=True,
        above_sma100=True,
        above_sma200=True,
    )
    return SignalResult(
        as_of=date(2026, 6, 8),
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
                trend=trend,
            )
        ],
        trends={"SMH": trend},
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
        warnings=[],
    )
