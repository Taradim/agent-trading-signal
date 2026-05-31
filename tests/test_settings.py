from pathlib import Path

import pytest

from agent_trading_signal.settings import load_portfolio, load_strategy_config, load_universe


def test_load_default_universe() -> None:
    universe = load_universe("config/universe.toml")

    assert universe.symbols == ["BTC", "ETH", "GLD", "SLV", "SMH", "QQQ", "SPY"]


def test_load_default_strategy_config() -> None:
    config = load_strategy_config("config/strategy.toml")

    assert config.signal.ema_window == 35
    assert config.signal.require_above_sma200_for_entries is True
    assert config.signal.entry_min_bullish_points == 1
    assert config.backtest.start.isoformat() == "2020-01-01"


def test_load_global_research_configs() -> None:
    global_universe = load_universe("config/universe_global_usd.toml")
    etf_universe = load_universe("config/universe_global_etf_2010.toml")
    core_universe = load_universe("config/universe_core_etf_2010.toml")
    recommended_universe = load_universe("config/universe_recommended.toml")
    config = load_strategy_config("config/strategy_2010.toml")
    recommended_config = load_strategy_config("config/strategy_recommended.toml")

    assert "ETH" in global_universe.symbols
    assert "ETH" not in etf_universe.symbols
    assert core_universe.symbols == ["GLD", "SLV", "SMH", "QQQ", "SPY"]
    assert recommended_universe.symbols == ["BTC", "GLD", "SLV", "SMH", "QQQ", "SPY"]
    assert config.backtest.start.isoformat() == "2010-01-01"
    assert recommended_config.backtest.start.isoformat() == "2016-01-01"
    assert recommended_config.backtest.decision_frequency == "2W-FRI"
    assert recommended_config.signal.entry_min_bullish_points == 3
    assert recommended_config.signal.tie_tolerance == 0


def test_active_assets_can_exclude_symbols() -> None:
    universe = load_universe("config/universe.toml")

    assets = universe.active_assets(["ETH", "SLV"])

    assert [asset.symbol for asset in assets] == ["BTC", "GLD", "SMH", "QQQ", "SPY"]


def test_load_current_portfolio() -> None:
    portfolio = load_portfolio("config/current_portfolio.toml")

    assert portfolio.allocation == {"CASH": 1.0}


def test_portfolio_requires_full_allocation(tmp_path: Path) -> None:
    path = tmp_path / "portfolio.toml"
    path.write_text("[allocation]\nBTC = 0.7\nSMH = 0.2\n", encoding="utf-8")

    with pytest.raises(ValueError, match="must sum to 1.0"):
        load_portfolio(path)
