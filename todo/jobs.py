import logging
from arq import cron
from arq.connections import RedisSettings

from todo.config import settings

logger = logging.getLogger(__name__)


async def welcome_user(ctx, username: str):
    """Runs in worker process."""
    logger.info("ARQ: sending welcome to %s", username)
    # later: real email provider


async def notify_task_created(ctx, user_id: int, title: str):
    logger.info("ARQ: user=%s created task=%s", user_id, title)


class WorkerSettings:
    functions = [welcome_user, notify_task_created]  # list of callables worker will be able to run (registry)
    redis_settings = RedisSettings(host=settings.REDIS_HOST, port=settings.REDIS_PORT)
    # optional: cron jobs later
