from agent_trading_signal.settings import load_strategy_config, load_universe


def test_load_default_universe() -> None:
    universe = load_universe("config/universe.toml")

    assert universe.symbols == ["BTC", "ETH", "GLD", "SLV", "SMH", "QQQ", "SPY"]


def test_load_default_strategy_config() -> None:
    config = load_strategy_config("config/strategy.toml")

    assert config.signal.ema_window == 35
    assert config.signal.require_above_sma200_for_entries is True
    assert config.signal.use_flip_flop_stabilizer is True
    assert config.signal.flip_flop_min_switches == 3
    assert config.backtest.start.isoformat() == "2020-01-01"


def test_active_assets_can_exclude_symbols() -> None:
    universe = load_universe("config/universe.toml")

    assets = universe.active_assets(["ETH", "SLV"])

    assert [asset.symbol for asset in assets] == ["BTC", "GLD", "SMH", "QQQ", "SPY"]
