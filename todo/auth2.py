# uses settings / config file to pull config values eg. secret key, token expiry etc.
import logging
from datetime import datetime, timedelta, timezone
from http.client import HTTPException
from typing import Optional

from argon2 import PasswordHasher
from fastapi import HTTPException, status
from jose import jwt, JWTError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from todo.config import settings

from todo.models import User, TokenBlacklist
from todo.schemas import UserCreate

ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)

# get logger
logger = logging.getLogger(__name__)  # __name__ gets name of current module. eg. in auth.py -> __name__ = "todo.auth"


# FAKE_USER = {
#     "id": 1,
#     "username": "dipen",
#     "hashed_password": "$argon2id$v=19$m=65536,t=3,p=4$r+VhnKISh2iR5FC5pr16pA$UeKicZSOqW8v5tb4t8dOUT0xAles5Bq+ciPaTDSeIQI"
# }


def hash_password(password: str) -> str:
    return ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return ph.verify(hashed_password, plain_password)
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()  # we do this so that the original data remains intact
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def get_user_by_username(db: Session, username: str):
    return db.query(User).where(User.username == username).first()


def create_user(db: Session, user_data: UserCreate) -> User:
    """
    Create a new user.
    Always forces role="user" — never trust the client.
    """
    # Check username
    if get_user_by_username(db, user_data.username):
        raise HTTPException(status_code=400, detail="Username already registered")

    # Check email (if provided)
    if user_data.email:
        existing_email = db.query(User).where(User.email == user_data.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

    hashed_password = hash_password(user_data.password)

    db_user = User(
        username=user_data.username,
        hashed_password=hashed_password,
        email=user_data.email,
        role="user",  # force this role = user here, (secure and correct way)
        is_active=True
    )
    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already exists"
        )
    except Exception as e:  # prevents leaking internal error details to the client while still logging the real problem
        db.rollback()
        # Log the real error for debugging
        logger.error("Unexpected error creating user: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not create user"
        )


def verify_token(token: str):
    """Decode JWT and return username"""

    # DEBUG
    # print(f"DEBUG SECRET_KEY", {settings.SECRET_KEY})
    # print(f"DEBUG ALGORITHM: {settings.ALGORITHM}")

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"}
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        print(f"DEBUG Payload: {payload}")  # DEBUG
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError as e:
        print(f"DEBUG JWTError: {e}")
        raise credentials_exception

    # We do not need to verify username is equal, We are trusting the signature of the JWT
    # (thanks to SECRET_KEY). If the token is valid, the username inside it is considered authentic.
    # Doing an extra DB lookup on every request would be expensive (performance hit).

    return username


def create_refresh_token(data: dict):
    """Create long-lived refresh token"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=7)  # 7 days
    to_encode.update({
        "exp": expire,
        "type": "refresh"  # Mark as refresh token
    })
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_refresh_token(token: str):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate refresh token"
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "refresh":
            raise credentials_exception
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
        return username
    except JWTError:
        raise credentials_exception


def blacklist_token(db: Session, token: str, expires_in_minutes: int = 30):
    """Add token to blacklist"""
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=expires_in_minutes)

    blacklisted = TokenBlacklist(
        token=token,
        expires_at=expires_at
    )
    db.add(blacklisted)
    db.commit()
