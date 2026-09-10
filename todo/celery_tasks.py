import logging
from datetime import datetime, timezone

from todo.celery_app import celery_app

# get logger
logger = logging.getLogger(__name__)  # __name__ gets name of current module. eg. in celery_tasks.py


def write_audit_log(username: str, action: str) -> None:
    """
        FastAPI BackgroundTasks: write an audit log entry.
        Runs after the API response is sent.
    """
    logger.info("AUDIT: user=%s action=%s", username, action)
    # Later we can extend this to:
    # - save to database
    # - send to external logging service
    # - etc.


# @celery_app.task:
# Registers the function as a Celery job
# Lets you call it with .delay() or .apply_async()
# Worker picks it up from Redis and runs it

@celery_app.task(name="todo.cleanup_expired_tokens")    #this task name is used by Celery to identify task to run
def cleanup_expired_tokens() -> str:
    """
    Celery task: delete expired rows from token_blacklist.
    Runs in a separate worker process.
    """
    # Keeping DB-related imports inside the task is common and acceptable.
    # Avoid circular imports: celery_app → tasks → database/models can create import cycles at startup
    # Celery worker safety: Worker imports task modules early; heavy/app imports inside the task are safer
    from todo.database import SessionLocal
    from todo.models import TokenBlacklist

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        deleted = (
            db.query(TokenBlacklist)
            .where(TokenBlacklist.expires_at < now)
            .delete(synchronize_session=False)
        )
        db.commit()
        msg = f"Deleted {deleted} expired blacklisted tokens"
        logger.info(msg)
        return msg
    except Exception as exc:
        db.rollback()
        logger.error("Token cleanup failed: %s", str(exc))
        raise  # ← raise the same exception again. Notifies Celery (otherwise it won't know if task failed)
    finally:
        db.close()
