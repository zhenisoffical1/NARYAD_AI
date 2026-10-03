import hashlib
import hmac
import secrets
import time
from dataclasses import dataclass
from datetime import timedelta

import jwt

from app.config import settings
from app.errors import TooManyRequests, Unauthorized
from app.models.base import utcnow
from app.models.enums import Role

_PIN_ITERATIONS = 120_000
_JWT_ALGORITHM = "HS256"


def hash_pin(pin: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt.encode(), _PIN_ITERATIONS)
    return f"pbkdf2_sha256${_PIN_ITERATIONS}${salt}${digest.hex()}"


def verify_pin(pin: str, pin_hash: str) -> bool:
    try:
        _, iterations, salt, expected = pin_hash.split("$")
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode(), salt.encode(), int(iterations))
    return hmac.compare_digest(digest.hex(), expected)


@dataclass(frozen=True, slots=True)
class TokenClaims:
    user_id: int
    role: Role


def create_access_token(user_id: int, role: Role) -> str:
    now = utcnow()
    payload = {
        "sub": str(user_id),
        "role": role.value,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_ttl_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_JWT_ALGORITHM)


def decode_access_token(token: str) -> TokenClaims:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[_JWT_ALGORITHM])
        return TokenClaims(user_id=int(payload["sub"]), role=Role(payload["role"]))
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise Unauthorized("Сессия истекла. Войдите заново по логину и ПИН.") from exc


class LoginThrottle:
    """Ограничение попыток входа: ПИН короткий, поэтому перебор надо останавливать.

    Хранится в памяти процесса — для одного экземпляра бэкенда этого достаточно.
    """

    def __init__(self, max_attempts: int, lock_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.lock_seconds = lock_seconds
        self._failures: dict[str, list[float]] = {}

    def check(self, login: str) -> None:
        now = time.monotonic()
        recent = [t for t in self._failures.get(login, []) if now - t < self.lock_seconds]
        self._failures[login] = recent
        if len(recent) >= self.max_attempts:
            wait_min = max(1, round((self.lock_seconds - (now - recent[0])) / 60))
            raise TooManyRequests(
                f"Слишком много неверных попыток. Повторите вход через {wait_min} мин "
                "или попросите мастера сбросить ПИН."
            )

    def fail(self, login: str) -> None:
        self._failures.setdefault(login, []).append(time.monotonic())

    def success(self, login: str) -> None:
        self._failures.pop(login, None)

    def reset(self) -> None:
        self._failures.clear()


login_throttle = LoginThrottle(settings.login_max_attempts, settings.login_lock_minutes * 60)
