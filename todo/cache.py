import json
import logging

import redis
from typing import Any, Optional
from todo.config import settings

# get logger
logger = logging.getLogger(__name__)  # __name__ = "todo.service"

# Connect to Redis

try:
    redis_client = redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,  # logical databases, using first - 0, like namespace inside Redis server
        decode_responses=True,  # return strings instead of bytes
        socket_connect_timeout=1,
        socket_timeout=1
    )

    # Test connection
    redis_client.ping()
    REDIS_AVAILABLE = True
except Exception as e:
    logger.warning("Redis not available: %s. Caching disabled.", str(e))
    redis_client = None
    REDIS_AVAILABLE = False


def get_cache(key: str) -> Optional[Any]:
    """Get value from cache"""
    if not REDIS_AVAILABLE:
        return None

    try:
        data = redis_client.get(key)
        if data is None:
            return None
        return json.loads(data)  # converts Json string into python object
    except Exception as e:
        logger.warning("Cache get failed: %s", str(e))
        return None


def set_cache(key: str, value: Any, expire: int | None = None) -> None:
    """
    Set value in cache
    expire = time in seconds
    """
    if not REDIS_AVAILABLE:
        return
    try:
        if expire is None:
            expire = settings.REDIS_EXPIRE_SECONDS

        redis_client.set(
            key,
            json.dumps(value, default=str),  # converts Python object -> JSON string. default=str handles datetime,
            ex=expire
        )
    except Exception as e:
        logger.warning("Cache set failed: %s", str(e))


def delete_cache(key: str) -> None:
    """Delete a specific cache key"""
    if not REDIS_AVAILABLE:
        return
    try:
        redis_client.delete(key)
    except Exception as e:
        logger.warning("Cache delete failed: %s", str(e))


def delete_pattern(pattern: str) -> None:
    """Delete all keys matching a pattern (e.g. tasks:*)"""
    if not REDIS_AVAILABLE:
        return
    try:
        keys = redis_client.keys(pattern)
        if keys:
            redis_client.delete(*keys)
    except Exception as e:
        logger.warning("Cache delete failed: %s", str(e))
