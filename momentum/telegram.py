"""Tiny Telegram Bot API client (plain HTTP, no framework)."""
from __future__ import annotations

import httpx

from . import config

API = "https://api.telegram.org/bot{token}/{method}"


def call(method: str, http_timeout: float = 30, **params):
    if not config.TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set (see .env.example)")
    r = httpx.post(API.format(token=config.TELEGRAM_BOT_TOKEN, method=method),
                   json=params, timeout=http_timeout)
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram {method} failed: {data}")
    return data["result"]


def send(chat_id, text: str, buttons: list[list[tuple[str, str]]] | None = None):
    params = {"chat_id": chat_id, "text": text}
    if buttons:
        params["reply_markup"] = {"inline_keyboard": [
            [{"text": label, "callback_data": data} for label, data in row] for row in buttons
        ]}
    return call("sendMessage", **params)


def clear_buttons(chat_id, message_id, new_text: str | None = None):
    try:
        if new_text:
            call("editMessageText", chat_id=chat_id, message_id=message_id, text=new_text)
        else:
            call("editMessageReplyMarkup", chat_id=chat_id, message_id=message_id,
                 reply_markup={"inline_keyboard": []})
    except RuntimeError:
        pass  # message too old or unchanged; not important


def answer_callback(callback_id: str, text: str = ""):
    try:
        call("answerCallbackQuery", callback_query_id=callback_id, text=text)
    except RuntimeError:
        pass


def get_updates(offset: int | None, timeout: int = 20):
    params = {"timeout": timeout, "allowed_updates": ["message", "callback_query"]}
    if offset is not None:
        params["offset"] = offset
    return call("getUpdates", http_timeout=timeout + 10, **params)
