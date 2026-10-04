"""Привязка Telegram к учётной записи через deep link `t.me/<бот>?start=<токен>`.

Параметр start в Telegram — до 64 символов из [A-Za-z0-9_-], поэтому JWT не подходит.
Токен — «id-срок-подпись» с HMAC на секрете сервера: хранить его не нужно, живёт 15 минут.
"""

import base64
import hashlib
import hmac
from datetime import datetime, timedelta

from app.config import settings
from app.errors import Conflict

LINK_TTL = timedelta(minutes=15)


def _sign(employee_id: int, expires: int) -> str:
    mac = hmac.new(
        settings.jwt_secret.encode(), f"tg:{employee_id}:{expires}".encode(), hashlib.sha256
    ).digest()
    return base64.urlsafe_b64encode(mac[:12]).decode().rstrip("=")


def make_token(employee_id: int, now: datetime) -> tuple[str, datetime]:
    expires_at = now + LINK_TTL
    expires = int(expires_at.timestamp())
    return f"{employee_id}-{expires}-{_sign(employee_id, expires)}", expires_at


def parse_token(token: str, now: datetime) -> int | None:
    """id сотрудника, если подпись верна и срок не вышел; иначе None."""
    try:
        raw_id, raw_exp, sig = token.split("-", 2)
        employee_id, expires = int(raw_id), int(raw_exp)
    except ValueError:
        return None
    if not hmac.compare_digest(sig, _sign(employee_id, expires)):
        return None
    if now.timestamp() > expires:
        return None
    return employee_id


def bot_link(token: str) -> str:
    if not (settings.telegram_bot_token and settings.telegram_bot_username):
        raise Conflict("Telegram-бот не подключён на сервере. Уведомления приходят в приложение.")
    return f"https://t.me/{settings.telegram_bot_username.lstrip('@')}?start={token}"
