from agent_trading_signal.settings import load_strategy_config, load_universe


def test_load_default_universe() -> None:
    universe = load_universe("config/universe.toml")

    assert universe.symbols == ["BTC", "ETH", "GLD", "SLV", "SMH", "QQQ", "SPY"]


def test_load_default_strategy_config() -> None:
    config = load_strategy_config("config/strategy.toml")

    assert config.signal.ema_window == 35
    assert config.backtest.start.isoformat() == "2020-01-01"
