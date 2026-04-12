"""
app/auth.py
===========
Authentication and authorisation layer.

  - Email + password login
  - bcrypt password hashing via passlib
  - JWT creation and validation via python-jose
  - FastAPI dependencies: get_current_user / require_admin
  - APIRouter mounted at /auth in main.py
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.orm import Session

from . import database as db_module
from .database import User, get_db

# ---------------------------------------------------------------------------
# Config (populated from .env via load_dotenv() in main.py)
# ---------------------------------------------------------------------------
SECRET_KEY : str = os.getenv("SECRET_KEY", "CHANGE_ME_GENERATE_WITH_secrets.token_hex_32")
ALGORITHM            = "HS256"
TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

# ---------------------------------------------------------------------------
# Security primitives
# ---------------------------------------------------------------------------
pwd_context   = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------
class RegisterRequest(BaseModel):
    email   : str = Field(..., description="Valid email address used to log in")
    password: str = Field(..., min_length=6, description="Minimum 6 characters")

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not _EMAIL_RE.match(v):
            raise ValueError("Invalid email address.")
        return v


class LoginResponse(BaseModel):
    access_token: str
    token_type  : str
    role        : str
    email       : str


class UserOut(BaseModel):
    id        : int
    email     : str
    role      : str
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------
def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------
def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    )
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------
def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db   : Session = Depends(get_db),
) -> User:
    """
    Decode the Bearer JWT, look up the user in the database.
    Raises HTTP 401 on any failure.
    """
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str | None = payload.get("sub")
        if not email:
            raise exc
    except JWTError:
        raise exc

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise exc
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Extend get_current_user — additionally enforces role == 'admin'.
    Raises HTTP 403 for non-admin users.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )
    return current_user


# ---------------------------------------------------------------------------
# Auth router  (prefix=/auth, mounted in main.py)
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> User:
    """
    Register a new user account.
    Email must be unique — returns HTTP 409 if already taken.
    All self-registered accounts receive role='user'.
    """
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"An account with email '{payload.email}' already exists.",
        )
    user = User(
        email           =payload.email,
        hashed_password =hash_password(payload.password),
        role            ="user",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=LoginResponse)
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db       : Session = Depends(get_db),
) -> dict:
    """
    Authenticate with email + password.
    The OAuth2 form sends credentials as 'username' (standard field name);
    we treat that value as the email address.
    Returns a signed JWT access token.
    """
    email = form_data.username.strip().lower()   # OAuth2 form field is 'username'
    user  = db.query(User).filter(User.email == email).first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )

    token = create_access_token(
        {"sub": user.email, "role": user.role},
        timedelta(minutes=TOKEN_EXPIRE_MINUTES),
    )
    return {
        "access_token": token,
        "token_type"  : "bearer",
        "role"        : user.role,
        "email"       : user.email,
    }