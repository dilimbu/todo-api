"""
Reusable FastAPI dependencies for authentication and other common logic.
Keep this file lightweight.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from todo.auth_sevice import verify_token
from todo.database import get_db
from todo.models import User as UserModel, TokenBlacklist
from todo.service import TodoService

# using OAuth2Password flow for authentication.
# tokenUrl specifies login endpoint eg. "/login" for swagger UI
# auto_error=True (default), automatically raises HTTP 401 if token is missing
oauth2_shema = OAuth2PasswordBearer(tokenUrl="/login", auto_error=False)


# Depends(oauth2_shema) = FastAPI looks for Authorization Bearer <token> header
# in request and extracts the token and passes it to function
def get_current_user(
        token: str = Depends(oauth2_shema),
        db: Session = Depends(get_db)) -> UserModel:
    """
    Dependency to extract and verify the current user from JWT token.
    Raises 401 if token is missing or invalid. Return full User object from DB.
    Used in all protected endpoints.
    """

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"}
        )
    try:
        # Check if token is blacklisted
        blacklisted = db.query(TokenBlacklist).where(TokenBlacklist.token == token).first()
        if blacklisted:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token has been revoked")

        username = verify_token(token)

        user = db.query(UserModel).where(UserModel.username == username).first()
        if not user:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
        if not user.is_active:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User is inactive")

        return user
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )


def get_current_active_user(current_user: str = Depends(get_current_user)):
    """Check if user is active"""
    # In real app, you would check DB
    return current_user


def get_current_admin_user(current_user: str = Depends(get_current_user)):
    """Check if the current user has admin role"""
    if current_user.role != "admin":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Admin access required"
        )
    return current_user


def get_todo_service(db: Session = Depends(get_db)) -> TodoService:
    """Dependency to get TodoService with DB session"""
    return TodoService(db)
