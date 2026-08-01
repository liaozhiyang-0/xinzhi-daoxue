from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    login: str
    display_name: str
    role: str
    status: str
    last_login_at: datetime | None
    created_at: datetime


class RegisterRequest(BaseModel):
    login: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=12, max_length=256)
    display_name: str = Field(default="", max_length=255)


class LoginRequest(BaseModel):
    login: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=256)


class RefreshRequest(BaseModel):
    refresh_token: str | None = Field(default=None, min_length=20, max_length=512)


class AuthSessionRead(BaseModel):
    account: AccountRead
    token_type: str = "Bearer"
    access_expires_at: datetime
    refresh_expires_at: datetime


class AuthMeRead(AccountRead):
    session_id: str
    access_expires_at: datetime


class GuestSessionRead(BaseModel):
    guest: Literal[True] = True
    user_id: str
    display_name: str = "游客"
    role: str = "guest"
    expires_at: datetime
