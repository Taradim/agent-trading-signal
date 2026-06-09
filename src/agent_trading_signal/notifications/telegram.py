from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class TelegramConfig:
    bot_token: str
    chat_id: str
    api_base_url: str = "https://api.telegram.org"


def telegram_config_from_env(env: Mapping[str, str] | None = None) -> TelegramConfig:
    values = os.environ if env is None else env
    bot_token = values.get("AGENT_TRADING_SIGNAL_TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = values.get("AGENT_TRADING_SIGNAL_TELEGRAM_CHAT_ID", "").strip()
    api_base_url = values.get("AGENT_TRADING_SIGNAL_TELEGRAM_API_BASE_URL", "").strip()

    missing = [
        name
        for name, value in [
            ("AGENT_TRADING_SIGNAL_TELEGRAM_BOT_TOKEN", bot_token),
            ("AGENT_TRADING_SIGNAL_TELEGRAM_CHAT_ID", chat_id),
        ]
        if not value
    ]
    if missing:
        raise ValueError("Missing Telegram environment variables: " + ", ".join(missing))

    return TelegramConfig(
        bot_token=bot_token,
        chat_id=chat_id,
        api_base_url=api_base_url or "https://api.telegram.org",
    )


def send_telegram_message(
    config: TelegramConfig,
    text: str,
    timeout_seconds: float = 10.0,
) -> None:
    payload = urlencode(
        {
            "chat_id": config.chat_id,
            "text": text,
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    url = f"{config.api_base_url.rstrip('/')}/bot{config.bot_token}/sendMessage"
    request = Request(
        url=url,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram API returned HTTP {error.code}: {detail}") from error
    except URLError as error:
        raise RuntimeError(f"Telegram API request failed: {error.reason}") from error

    try:
        decoded = json.loads(body)
    except json.JSONDecodeError as error:
        raise RuntimeError("Telegram API returned invalid JSON") from error

    if not decoded.get("ok"):
        description = decoded.get("description", "unknown error")
        raise RuntimeError(f"Telegram API rejected the message: {description}")
