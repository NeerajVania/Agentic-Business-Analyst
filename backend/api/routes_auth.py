"""
backend/api/routes_auth.py
===========================
Authentication endpoints.

  POST /auth/register  — create account, returns JWT
  POST /auth/token     — login with OAuth2 password form, returns JWT
  GET  /auth/me        — return current user profile

Not directly called from Streamlit pages but required when
settings.require_auth = True. The JWT is stored client-side and
passed as Bearer token in the Authorization header.
"""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from backend.models.schemas import RegisterRequest, TokenResponse, UserProfile
from backend.utils.security import (
    authenticate_user,
    create_access_token,
    get_current_active_user,
    get_user,
    hash_password,
)
from database.session import UserModel, get_db
from config.settings import get_settings

settings = get_settings()
router = APIRouter()


@router.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    """Register a new user and return a JWT access token."""
    duplicate = await db.execute(
        select(UserModel).where(
            or_(UserModel.username == request.username, UserModel.email == request.email)
        )
    )
    if duplicate.scalars().first() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with that username or email already exists.",
        )

    user = UserModel(
        username=request.username,
        email=request.email,
        hashed_password=hash_password(request.password),
        role=request.role or "user",
    )
    db.add(user)
    try:
        await db.commit()
        await db.refresh(user)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to register user. Please choose another username or email.",
        )

    access_token = create_access_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        username=user.username,
        email=user.email,
        role=user.role,
    )


@router.post("/token", response_model=TokenResponse)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """OAuth2 password-grant login. Returns JWT."""
    user = await authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role},
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        username=user.username,
        email=user.email,
        role=user.role,
    )


@router.get("/me", response_model=UserProfile)
async def read_users_me(current_user: UserProfile = Depends(get_current_active_user)) -> UserProfile:
    """Return the current authenticated user's profile."""
    return current_user