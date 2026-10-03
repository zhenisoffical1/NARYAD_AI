from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Role, Shift


class LoginRequest(BaseModel):
    login: str = Field(min_length=1, max_length=40)
    pin: str = Field(pattern=r"^\d{4}$")


class EmployeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    login: str
    full_name: str
    short_name: str
    role: Role
    specialty: str | None
    grade: int | None
    brigade_id: int | None
    shift: Shift | None
    on_shift: bool
    telegram_linked: bool = False


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: EmployeeOut
