"""Authentication routes: register, login, token refresh, current user."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Deque, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.entities import DEFAULT_MATCHING_WEIGHTS, User
from app.schemas.auth import (
    CustomATSBoard,
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Simple in-process brute-force throttle for failed logins (per email and per client IP).
LOGIN_MAX_FAILURES = 10
LOGIN_WINDOW_SECONDS = 15 * 60
_failed_logins: Dict[str, Deque[float]] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _recent_failures(key: str, now: float) -> int:
    q = _failed_logins.get(key)
    if not q:
        return 0
    while q and now - q[0] > LOGIN_WINDOW_SECONDS:
        q.popleft()
    if not q:
        _failed_logins.pop(key, None)
        return 0
    return len(q)


def serialize_user(user: User) -> UserResponse:
    boards = [CustomATSBoard(**b) for b in (user.custom_ats_boards_json or [])]
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        theme_preference=user.theme_preference,
        data_retention_days=user.data_retention_days,
        default_weights=user.default_weights_json or dict(DEFAULT_MATCHING_WEIGHTS),
        custom_ats_boards=boards,
        created_at=user.created_at,
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    normalized_email = payload.email.strip().lower()
    existing = await db.execute(select(User).where(User.email == normalized_email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        email=normalized_email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        role="user",
        default_weights_json=dict(DEFAULT_MATCHING_WEIGHTS),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return TokenResponse(
        access_token=create_access_token(user.id, user.role),
        refresh_token=create_refresh_token(user.id, user.role),
        user=serialize_user(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    normalized_email = payload.email.strip().lower()
    now = time.monotonic()
    keys = (f"email:{normalized_email}", f"ip:{_client_ip(request)}")
    if any(_recent_failures(k, now) >= LOGIN_MAX_FAILURES for k in keys):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please wait 15 minutes and try again.",
        )
    res = await db.execute(select(User).where(User.email == normalized_email))
    user = res.scalar_one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        for k in keys:
            _failed_logins[k].append(now)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled.",
        )
    for k in keys:
        _failed_logins.pop(k, None)

    return TokenResponse(
        access_token=create_access_token(user.id, user.role),
        refresh_token=create_refresh_token(user.id, user.role),
        user=serialize_user(user),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_tokens(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    decoded = decode_token(payload.refresh_token)
    if not decoded or decoded.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token.",
        )

    user_id = decoded.get("sub")
    res = await db.execute(select(User).where(User.id == user_id))
    user = res.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found.",
        )

    return TokenResponse(
        access_token=create_access_token(user.id, user.role),
        refresh_token=create_refresh_token(user.id, user.role),
        user=serialize_user(user),
    )


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return serialize_user(current_user)
