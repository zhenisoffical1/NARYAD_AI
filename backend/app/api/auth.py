from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import get_current_user
from app.errors import Unauthorized
from app.models import Employee
from app.schemas.auth import EmployeeOut, LoginRequest, TokenResponse
from app.security import create_access_token, login_throttle, verify_pin

router = APIRouter(prefix="/auth", tags=["Вход"])


def employee_out(user: Employee) -> EmployeeOut:
    out = EmployeeOut.model_validate(user)
    out.telegram_linked = user.telegram_chat_id is not None
    return out


@router.post("/login", response_model=TokenResponse, summary="Вход по логину и ПИН")
async def login(body: LoginRequest, session: AsyncSession = Depends(get_session)) -> TokenResponse:
    login_key = body.login.strip().lower()
    login_throttle.check(login_key)

    user = await session.scalar(select(Employee).where(Employee.login == login_key))
    if user is None or not user.is_active or not verify_pin(body.pin, user.pin_hash):
        login_throttle.fail(login_key)
        raise Unauthorized("Неверный логин или ПИН. Проверьте и попробуйте ещё раз.")

    login_throttle.success(login_key)
    return TokenResponse(
        access_token=create_access_token(user.id, user.role), user=employee_out(user)
    )


@router.get("/me", response_model=EmployeeOut, summary="Текущий пользователь")
async def me(user: Employee = Depends(get_current_user)) -> EmployeeOut:
    return employee_out(user)
