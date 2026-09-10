import logging
# threading related
from contextlib import asynccontextmanager

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

from todo import redis_utils
from todo.config import settings
from todo.exceptions import (
    validation_exception_handler,
    http_exception_handler,
    rate_limit_exceeded_handler
)
from todo.logging_config import setup_logging
from todo.routers import auth, tasks, admin, reports, health, dashboard

# ====================== Initialize Logging ======================
setup_logging()
logger = logging.getLogger(__name__)


# =========== Application lifespan (startup / shutdown) ============

@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- startup (before any request) ---
    try:
        # creates new redis pool
        redis_utils.redis_pool = await create_pool(
            RedisSettings(host=settings.REDIS_HOST, port=settings.REDIS_PORT)
        )
        logger.info("ARQ Redis pool ready")
    except Exception as e:
        # Non-critical: API should still start if Redis/queue is down
        redis_utils.redis_pool = None
        logger.warning("ARQ Redis pool unavailable — jobs disabled: %s", e)

    yield
    # --- shutdown (after server stops) ---
    if redis_utils.redis_pool is not None:
        await redis_utils.redis_pool.close()
        logger.info("ARQ Redis pool closed")
    else:
        logger.info("ARQ Redis pool was not started — nothing to close")


app = FastAPI(title="Secure Todo API", lifespan=lifespan)

# ====================== CORS ======================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# ====================== Global Exception Handlers ======================
# registering exception handler
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # Rate limit handler

# ====================== Router registration ======================
app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(admin.router)
app.include_router(reports.router)
app.include_router(health.router)
app.include_router(dashboard.router)
