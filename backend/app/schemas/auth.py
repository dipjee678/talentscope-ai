"""Authentication and user settings schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class CustomATSBoard(BaseModel):
    provider: str = Field(..., pattern="^(greenhouse|lever|ashby)$")
    slug: str = Field(..., min_length=1, max_length=100)
    company_name: str = Field(..., min_length=1, max_length=150)


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    theme_preference: str
    data_retention_days: int
    default_weights: Dict[str, float]
    custom_ats_boards: List[CustomATSBoard] = []
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class SettingsUpdateRequest(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=200)
    theme_preference: Optional[str] = Field(default=None, pattern="^(light|dark|system)$")
    data_retention_days: Optional[int] = Field(default=None, ge=7, le=3650)
    default_weights: Optional[Dict[str, float]] = None
    custom_ats_boards: Optional[List[CustomATSBoard]] = None
