import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from todo.database import get_db
from todo.dependencies import get_current_user
from todo.models import User as UserModel
from todo.rate_limiter import limiter

import todo.redis_utils as redis_utils

from todo.schemas import Token, TokenRefresh, User, UserCreate
# adjust imports to your real module names:
from todo.auth_sevice import (
    create_user,
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
    blacklist_token,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login", auto_error=False)


@router.post("/register", response_model=User, status_code=201)
@limiter.limit("10/minute")  # Rate limit registration
async def register(
        request: Request,
        user_data: UserCreate,
        db: Session = Depends(get_db),
):
    """Register a new user with rate limiting+ welcome side effect."""
    try:
        new_user = create_user(db, user_data) # user + outbox
        logger.info("New user registered: %s", user_data.username)

        # will be performing welcome message via kafka topic:
        # # Redis job, worker process
        # if redis_utils.redis_pool is not None:
        #     await redis_utils.redis_pool.enqueue_job("welcome_user", new_user.username)
        # else:
        #     logger.warning(
        #         "Redis pool unavailable - skipped welcome job for %s",
        #         new_user.username,
        #     )
        return new_user
    except HTTPException as e:
        # for better performance use %s with logging, f-string evaluates expression immediately
        logger.warning("Registration failed for %s: %s", user_data.username, e.detail)
        raise e


@router.post("/login")
@limiter.limit("5/minute")
async def login(
        request: Request,
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: Session = Depends(get_db),
):
    """Login and get JWT token with rate limiting + for refresh tokens"""

    # get user from db via username
    user = db.query(UserModel).where(UserModel.username == form_data.username).first()

    # if user does not exist or invalid password
    if not user or not verify_password(form_data.password, user.hashed_password):
        logger.warning("Failed login attempt for username: %s", form_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create both tokens
    token = create_access_token({"sub": user.username})
    refresh_token = create_refresh_token({"sub": user.username})

    logger.info("User logged in: %s", user.username)
    return {
        "access_token": token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/refresh", response_model=Token)
async def refresh_token(
        token_refresh: TokenRefresh,
        db: Session = Depends(get_db),
):
    """Get new access token using refresh token"""
    username = verify_refresh_token(token_refresh.refresh_token)

    # Optional: Check if user still exists and is active, note: using UserModel (SQLAlchemy)
    user = db.query(UserModel).where(UserModel.username == username).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")

    # Create new access token
    new_access_token = create_access_token({"sub": username})
    return {
        "access_token": new_access_token,
        "refresh_token": token_refresh.refresh_token,
        "token_type": "bearer",
    }


@router.post("/logout")
@limiter.limit("10/minute")
async def logout(
        request: Request,
        token: str = Depends(oauth2_scheme),
        refresh_data: TokenRefresh | None = None,
        db: Session = Depends(get_db),
        current_user: UserModel = Depends(get_current_user),
):
    """Logout and blacklist the current access token"""
    # Blacklist access token
    if token:
        blacklist_token(db, token)
        logger.info("User %s logged out", current_user.username)

    # Also blacklist refresh token if provided
    if refresh_data and refresh_data.refresh_token:
        blacklist_token(db, refresh_data.refresh_token)

    return {"message": "Successfully logged out"}
