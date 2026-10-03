"""Доменные ошибки. Текст — для человека: что случилось и что делать, на русском, без извинений."""


class DomainError(Exception):
    status_code = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFound(DomainError):
    status_code = 404


class Forbidden(DomainError):
    status_code = 403


class Conflict(DomainError):
    """Недопустимый переход статуса или конфликт состояния."""

    status_code = 409


class Invalid(DomainError):
    status_code = 422


class Unauthorized(DomainError):
    status_code = 401


class TooManyRequests(DomainError):
    status_code = 429
