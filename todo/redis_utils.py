"""Shared ARQ Redis pool + health ping. Pool is set from main lifespan."""
import logging

logger = logging.getLogger(__name__)

redis_pool = None  # assigned in lifespan

# testing - async Redis check

async def ping_redis() -> bool:
    """Lightweight check: is the shared ARQ Redis pool usable?"""
    if redis_pool is None:
        # Soft-fail path: lifespan never got a pool
        return False
    try:
        pong = await redis_pool.ping()
        # if boolean True -> success, else if bytes PONG -> success, or if string PONG -> success, else -> False
        return pong is True or pong == b"PONG" or pong == "PONG"
    except Exception as e:
        logger.warning("Redis ping failed: %s", e)
        return False
