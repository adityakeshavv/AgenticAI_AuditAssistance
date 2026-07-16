from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AuthUser(BaseModel):
    user_id: str
    full_name: str
    email: str
    auth_provider: str
    role: str = "user"
    is_active: bool = True
    last_login_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class SignupRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class AuthResponse(BaseModel):
    success: bool = True
    access_token: str
    token_type: str = "bearer"
    user: AuthUser


class MeResponse(AuthUser):
    pass


class UserStatusUpdate(BaseModel):
    is_active: bool
