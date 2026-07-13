"""
backend/utils/security.py
==========================
JWT token generation, verification, password hashing, and FastAPI
dependency functions for authentication.

Used by
-------
  main.py              — get_current_active_user in protected_dependencies
  routes_auth.py       — authenticate_user, create_access_token, hash_password
  routes_auth.py       — get_user
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from config.settings import get_settings
from database.session import UserModel, get_db

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


# ── Pydantic models ───────────────────────────────────────────────────────────

class TokenData(BaseModel):
    sub: str
    role: Optional[str] = "user"
    exp: datetime
    iat: datetime


class User(BaseModel):
    username: str
    email: EmailStr
    role: str = "user"
    disabled: bool = False


class UserInDB(User):
    hashed_password: str


# ── Password helpers ──────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# ── Token helpers ─────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Encode a JWT with exp and iat claims."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)


def verify_token(token: str) -> Optional[str]:
    """Decode JWT and return the subject (username), or None if invalid."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload.get("sub")
    except JWTError as exc:
        logger.warning("Invalid token: {}", exc)
        return None


# ── DB helpers ────────────────────────────────────────────────────────────────

async def get_user(db: AsyncSession, username: str) -> Optional[UserInDB]:
    result = await db.execute(select(UserModel).where(UserModel.username == username))
    user = result.scalars().first()
    if not user:
        return None
    return UserInDB(
        username=user.username,
        email=user.email,
        role=user.role,
        hashed_password=user.hashed_password,
    )


async def authenticate_user(db: AsyncSession, username: str, password: str) -> Optional[UserInDB]:
    user = await get_user(db, username)
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


# ── FastAPI dependencies ──────────────────────────────────────────────────────

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    username = verify_token(token)
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = await get_user(db, username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return User(username=user.username, email=user.email, role=user.role)


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.disabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    return current_user