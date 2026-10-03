from collections.abc import Awaitable, Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import Forbidden, Unauthorized
from app.models import Employee
from app.models.enums import Role
from app.security import decode_access_token

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> Employee:
    if credentials is None:
        raise Unauthorized("Нужен вход: введите логин и ПИН.")
    claims = decode_access_token(credentials.credentials)
    user = await session.get(Employee, claims.user_id)
    if user is None or not user.is_active:
        raise Unauthorized("Учётная запись отключена. Обратитесь к администратору.")
    return user


def require_role(*roles: Role) -> Callable[..., Awaitable[Employee]]:
    """Зависимость FastAPI: пускает только перечисленные роли."""
    allowed = frozenset(roles)

    async def dependency(user: Employee = Depends(get_current_user)) -> Employee:
        if user.role not in allowed:
            raise Forbidden("Этот раздел недоступен для вашей роли.")
        return user

    return dependency
