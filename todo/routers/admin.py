import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from todo.database import get_db
from todo.dependencies import get_current_admin_user
from todo.models import User as UserModel
from todo.rate_limiter import limiter
from todo.schemas import User
from todo.celery_tasks import cleanup_expired_tokens

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[User])
@limiter.limit("10/minute")
async def list_all_users(
        request: Request,
        db: Session = Depends(get_db),
        current_user: UserModel = Depends(get_current_admin_user),
):
    """
    Only users with role = "admin" can access this.
    """
    users = db.query(UserModel).all()
    logger.info("Admin %s accessed user list", current_user.username)
    return users


@router.post("/cleanup-tokens")
@limiter.limit("5/minute")
async def trigger_token_cleanup(
        request: Request,
        current_user: UserModel = Depends(get_current_admin_user),
):
    """
    queue expired token cleanup in Celery.
    Returns immediately; work runs in the worker.
    """

    # send job to background worker queue (Celery related), don't execute here
    task = cleanup_expired_tokens.delay()
    logger.info(
        "Admin %s triggered token cleanup. task_id=%s",
        current_user.username,
        task.id,
    )
    # NOTE: FastAPI doesn't need return type, this dict is automatically converted to JSON
    # optionally we can specify return type eg. response_model = CleanupResponse
    return {"message": "Token cleanup started", "task_id": task.id}
