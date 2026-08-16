from celery import Celery
from todo.config import settings

celery_app = Celery(
    "todo_worker",  # name of Celery app (for logs/identification)
    broker=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}", # Where tasks are queued (Redis). Producers put jobs here; workers read from here
    backend=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}", # Where results are stored (also Redis). Optional, but useful if you want task results
    include=["todo.tasks"]  # where tasks functions live. Tells Celery which modules contain task functions
)

# NOTE: We’re using the same Redis instance for both (common for learning/small apps).

celery_app.conf.update(
    task_serializer="json", # Tasks are sent as JSON
    result_serializer="json", # Results stored as JSON
    accept_content=["json"], # Only accept JSON (safer)
    timezone="UTC", # Use UTC for schedules
    enable_utc=True, # Prefer UTC timestamps
    # Celery Beat (automatic schedule)
    beat_schedule={
        # Run cleanup every hour
        "cleanup-expired-tokens-hourly": {
            "task": "todo.cleanup_expired_tokens",  # task to be queued, that will be run by worker
            "schedule": 5, # TESTING for 1 sec #  3600.0, # seconds (1 hour) - beat queues todo.cleanup_expired_tokens
            # Or use crontab: crontab(minute=0) # every hour at minute 0
        }
    }
)
