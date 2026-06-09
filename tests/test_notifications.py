import pytest

from agent_trading_signal.notifications.telegram import telegram_config_from_env


def test_telegram_config_from_env_reads_namespaced_values() -> None:
    config = telegram_config_from_env(
        {
            "AGENT_TRADING_SIGNAL_TELEGRAM_BOT_TOKEN": " token ",
            "AGENT_TRADING_SIGNAL_TELEGRAM_CHAT_ID": " chat ",
        }
    )

    assert config.bot_token == "token"
    assert config.chat_id == "chat"
    assert config.api_base_url == "https://api.telegram.org"


def test_telegram_config_from_env_requires_secret_values() -> None:
    with pytest.raises(ValueError, match="AGENT_TRADING_SIGNAL_TELEGRAM_BOT_TOKEN"):
        telegram_config_from_env({})
