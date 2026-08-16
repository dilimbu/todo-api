# main v2 - uses auth2.py
import logging

# threading related
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

from arq import create_pool
from arq.connections import RedisSettings

from fastapi import FastAPI, Depends, HTTPException, status, Request, BackgroundTasks
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from slowapi.errors import RateLimitExceeded
from sqlalchemy.orm import Session

from todo.auth2 import (
    create_access_token,
    verify_password,
    create_user,
    create_refresh_token,
    verify_refresh_token,
    blacklist_token
)
from todo.config import Settings, settings
from todo.database import get_db
from todo.dependencies import get_current_user, get_current_admin_user
from todo.exceptions import (
    validation_exception_handler,
    http_exception_handler,
    rate_limit_exceeded_handler
)
from todo.logging_config import setup_logging
from todo.models import User as UserModel  # SQLAlchemy model
from todo.rate_limiter import limiter  # Rate limiter
from todo.schemas import Task, TaskCreate, User, UserCreate, Token, TokenRefresh
from todo.service import TodoService

from todo.tasks import write_audit_log, cleanup_expired_tokens

# ====================== Initialize Logging ======================
setup_logging()
logger = logging.getLogger(__name__)  # __name__ gets name of current module. eg. in main2.py -> __name__ = "todo.main2"

# ====================== ARQ Redis pool ======================
redis_pool = None  # set on startup; used to enqueue jobs


# lifespan is the real-world FastAPI pattern for startup/shutdown
# Creating an ARQ/Redis pool there is best practice. Making startup hard-fail
# without Redis is fine when Redis is required; for learning, soft-fail is optional.

# 1. If Redis job queue (ARQ/Celery) and jobs matter, we "fail" startup (hence no silent catching)
# 2. If Redis is cache onlyUsually start without it and degrade (DB still works)

# Redis pool - collection of reusable Redis connections that application manages, instead
# of opening new connection to Redis every time you need to talk to, keep pool of already
# open connections and reuse them. Low overhead, much faster and scalable, controlled number of connections

@asynccontextmanager
async def lifespan(app: FastAPI):
    global redis_pool
    # --- startup (before any request) ---
    try:
        # creates new redis pool
        redis_pool = await create_pool(
            RedisSettings(host=settings.REDIS_HOST, port=settings.REDIS_PORT)
        )
        logger.info("ARQ Redis pool ready")
    except Exception as e:
        # Non-critical: API should still start if Redis/queue is down
        redis_pool = None
        logger.warning("ARQ Redis pool unavailable — jobs disabled: %s", e)

    yield
    # --- shutdown (after server stops) ---
    if redis_pool is not None:
        await redis_pool.close()
        logger.info("ARQ Redis pool closed")
    else:
        logger.info("ARQ Redis pool was not started — nothing to close")


app = FastAPI(title="Secure Todo API", lifespan=lifespan)

# ====================== CORS ======================
# CORS - Cross-origin resource sharing
# Allows frontend apps to call this API
# prevents FE app (react, angular etc.) running in one domain from calling backend API running on another domain
# unless you explicitly allow it
# middleware should usually be added right after creating app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    # which websites can access API (Restrict in production eg. https://myfrontend.com, "http://localhost:3000")
    allow_credentials=True,  # allows cookies, auth headers, keep True if using JWT/Cookies
    allow_methods=["*"],  # allow HTTP methods, in PROD use eg. ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    allow_headers=["*"]  # allow request headers
)

# ====================== Global Exception Handlers ======================
# registering exception handler
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)  # Rate limit handler

# ====================== Thread pool for short blocking work ======================
blocking_pool = ThreadPoolExecutor(max_workers=4)


def blocking_report_job(user_id: int) -> dict:
    """
    Simulate blocking work (legacy SDK, file I/O, sync HTTP client, etc.).
    Runs in a worker thread — not on the asyncio event loop.
    """
    import time
    time.sleep(5)  # pretend slow blocking work
    return {
        "user_id": user_id,
        "report": "done",
        "source": "thread-pool"
    }


# ====================== Dependencies ======================
def get_todo_service(db: Session = Depends(get_db)):
    """Dependency to get TodoService with DB session"""
    return TodoService(db)


# ====================== Auth Endpoints ======================
@app.post("/register", response_model=User, status_code=201)
@limiter.limit("10/minute")  # Rate limit registration
async def register(
        request: Request,
        user_data: UserCreate,
        # background_tasks: BackgroundTasks,  we will be using ARQ instead
        db: Session = Depends(get_db)):
    """Register a new user with rate limiting+ welcome side effect."""
    try:
        new_user = create_user(db, user_data)
        logger.info("New user registered: %s", user_data.username)

        # commented plain task: will be using ARQ enqueue as below with redis
        # Step 2 — same process, after response (good for demos / light work)
        # Runs after 201 is returned — user does not wait for sleep(1)
        # background_tasks.add_task(write_welcome_log, new_user.username)

        # Step 4 - Redis job, worker process (durable)
        if redis_pool is not None:
            await redis_pool.enqueue_job("welcome_user", new_user.username)
        else:
            logger.warning("Redis pool unavailable - skipped welcome job for %s", new_user.username)
        return new_user

        # do not use: logger.info(f"user registered {user_data.username}")
        # f-string evaluates expression immediately, even if log level is set
        # to warning. %s only formats string, if log level is enabled,
        # for better performance use %s with logging
    except HTTPException as e:
        logger.warning("Registration failed for %s: %s", user_data.username, e.detail)
        raise e


# def write_welcome_log(username: str):
#     """Simulated slow side effect — runs after the response is sent."""
#     import time
#     time.sleep(1)  # pretend email/SMS work
#     logger.info("BackgroundTasks: Welcome email sent to %s", username)


@app.post("/login")
@limiter.limit("5/minute")  # Strict limit on login (anti-brute force), Request param needed for slowapi rate limit
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(),
                db: Session = Depends(get_db)):
    """Login and get JWT token with rate limiting + for refresh tokens"""

    # get user from db via username
    user = db.query(UserModel).where(UserModel.username == form_data.username).first()

    # if user does not exist or invalid password
    if not user or not verify_password(form_data.password, user.hashed_password):
        logger.warning("Failed login attempt for username: %s", form_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Create both tokens
    token = create_access_token({"sub": user.username})
    refresh_token = create_refresh_token({"sub": user.username})

    logger.info("User logged in: %s", user.username)
    return {
        "access_token": token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@app.post("/refresh", response_model=Token)
async def refresh_token(token_refresh: TokenRefresh, db: Session = Depends(get_db)):
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
        "refresh_token": token_refresh.refresh_token,  # Return same refresh token
        "token_type": "bearer"
    }


oauth2_shema = OAuth2PasswordBearer(tokenUrl="/login", auto_error=False)


@app.post("/logout")
@limiter.limit("10/minute")
async def logout(
        request: Request,
        token: str = Depends(oauth2_shema),
        refresh_data: TokenRefresh | None = None,  # optional body
        db: Session = Depends(get_db),
        current_user: UserModel = Depends(get_current_user)
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


# ====================== Protected Task Endpoints ======================
@app.get("/tasks", response_model=list[Task])
@limiter.limit("30/minute")
async def list_tasks(
        request: Request,
        show_all: bool = False,
        service: TodoService = Depends(get_todo_service),
        curr_user: UserModel = Depends(get_current_user)
):
    """List tasks"""
    logger.info("User %s requested tasks (show_all=%s)", curr_user.username, show_all)
    return service.get_all(curr_user.id, show_all)


@app.post("/tasks", response_model=Task, status_code=201)
@limiter.limit("30/minute")
async def create_task(
        request: Request,
        task: TaskCreate,
        background_tasks: BackgroundTasks,
        service: TodoService = Depends(get_todo_service),
        current_user: UserModel = Depends(get_current_user)
):
    """Create a new task"""
    new_task = service.create(current_user.id, task)
    # logger.info("User %s created task: %s", current_user.username, task.title)

    # simple fast API background task, runs after response is sent
    background_tasks.add_task(
        write_audit_log,  # function to call
        current_user.username,  # first arg
        f"created_task:{new_task.id}"  # second arg
    )

    return new_task


@app.patch("/tasks/{task_id}/done", response_model=Task)
@limiter.limit("30/minute")
async def mark_as_done(
        request: Request,
        task_id: int,
        service: TodoService = Depends(get_todo_service),
        current_user: UserModel = Depends(get_current_user)
):
    """Mark task as done"""
    task = service.mark_done(current_user.id, task_id)
    if not task:
        logger.warning("Error setting task %s done : %s", task_id)
        raise HTTPException(status_code=404, detail="Task not found")
    logger.info("User %s marked task %s as done", current_user.username, task.title)
    return task


@app.delete("/tasks/{task_id}")
@limiter.limit("30/minute")
async def delete_task(request: Request, task_id: int,
                      service: TodoService = Depends(get_todo_service),
                      current_user: UserModel = Depends(get_current_user)):
    """Delete a task"""
    if service.delete(current_user.id, task_id):
        logger.info("User %s deleted task %s", current_user.username, task_id)
        return {"message": "Task deleted successfully"}

    logger.warning("Task %s not found by user %s", task_id, current_user.username)
    raise HTTPException(status_code=404, detail="Task not found")


# ====================== DAY 16: Blocking work offloaded to thread pool ======================
@app.get("/reports/blocking/{user_id}")
async def generate_report(user_id: int):
    """
    Offload blocking work to a thread so the asyncio event loop stays free.
    Other requests (e.g. GET /health) can still be handled while this runs.
    """

    # if you just this normally, it will block other api call since it will wait for sleep(5)
    # and no other request can be processed hence whole API feels frozen for that request duration
    # with run_in_executor(), sleep runs in "worker thread", event loop is freed immediately after
    # scheduling the work
    #  result = blocking_report_job(user_id)

    # NOTE: even for async def tasks if we want non blocking CPU then we must use
    # run_in_executor, becase async await only helps with "waiting" not with blocking CPU or time.sleep etc.
    # async / await lets even loop switch to another request while you are waiting on I/O:
    # network response, database query (async driver), Redis, await asyncio.sleep(...)

    loop = asyncio._get_running_loop()
    try:
        result = await loop.run_in_executor(
            blocking_pool,  # thread pool
            blocking_report_job,  # callable
            user_id  # arg passed to callable
        )
        return result
    except ValueError as e:
        # expected / business error
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        # unexpected failure
        logger.exception("Report failed for user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="Report generation failed")


# ====================== Admin Endpoints ======================
@app.get("/admin/users", response_model=list[User])
@limiter.limit("10/minute")
async def list_all_users(
        request: Request,
        db: Session = Depends(get_db),
        current_user: UserModel = Depends(get_current_admin_user)):
    """
    Admin-only endpoint.
    Only users with role = "admin" can access this.
    """
    users = db.query(UserModel).all()
    logger.info("Admin %s accessed user list", current_user.username)
    return users


@app.post("/admin/cleanup-tokens")
@limiter.limit("5/minute")
async def trigger_token_cleanup(
        request: Request,
        current_user: UserModel = Depends(get_current_admin_user)
):
    """
    Admin-only: queue expired token cleanup in Celery.
    Returns immediately; work runs in the worker.
    """
    task = cleanup_expired_tokens.delay()  # send job to background worker queue (Celery related), don't execute here

    logger.info(
        "Admin %s triggered token cleanup. task_id=%s",
        current_user.username,
        task.id
    )
    # FastAPI doesn't need return type, this dict is automatically converted to JSON
    # optionally we can specify return type eg. response_model = CleanupResponse
    return {
        "message": "Token cleanup started",
        "task_id": task.id
    }


# ====================== Health Check ======================
@app.get("/health")
async def health():
    """Health check endpoint for Docker and monitoring"""
    return {"status": "healthy", "service": "todo-api"}

# The Refresh Flow in Practice:

# The actual call to /refresh is usually done automatically by the frontend (not in backend code).

# Backend only provides the endpoint.
# Frontend (JavaScript) example:

# // Axios interceptor (frontend)
# axios.interceptors.response.use(
#   response => response,
#   async error => {
#     if (error.response.status === 401) {
#       try {
#         const refreshResponse = await axios.post('/refresh', {
#           refresh_token: localStorage.getItem('refresh_token')
#         });
#
#         const newAccessToken = refreshResponse.data.access_token;
#         localStorage.setItem('access_token', newAccessToken);
#
#         // Retry original request with new token
#         error.config.headers.Authorization = `Bearer ${newAccessToken}`;
#         return axios(error.config);
#       } catch (refreshError) {
#         // Logout user
#         localStorage.clear();
#       }
#     }
#     return Promise.reject(error);
#   }
# );


# =====================================================
# Python Mastery Project:
# =====================================================

# Day 1: Pythonic Basics & Idioms
# List/dict/set comprehensions & generator expressions
# collections (defaultdict, Counter, deque, dataclass)
# Unpacking, enumerate, zip, itertools, match statement
# pathlib, f-strings, walrus operator (:=)
# Hands-on: Build a clean CLI Task Manager (todo.py) using typer or argparse.
# Use dataclasses, comprehensions, and JSON persistence.

# ===============
# Day 2: Functions & Python Magic:
# Goal: Learn how to write clean, powerful, and Pythonic functions.
# Topics to Focus On (Most Important)
# *args & **kwargs
# Closures and nonlocal
# Decorators (with and without arguments) ← Most important for today
# Generators (yield) and yield from
# Context Managers (@contextmanager)
# Magic methods (__str__, __len__, __getitem__, __call__)
# Hands-on: Add these to your todo app:
# @timer and @backup decorators
# Generator for large task history
# Context manager for safe file operations

# ===============
# Day 3: Modern OOP & Typing
# Goal: Learn how to write clean, professional, and maintainable object-oriented
# code in Python (the modern way).
# Topics for Day 3
# 1. @dataclass in depth (fields, field(), init=False, etc.)
# 2. Composition over Inheritance
# 3. Protocols (Structural Typing) – very Pythonic
# 4. Type Hints deeply (List, Dict, Optional, Union, Generic)
# 5. Magic methods (__str__, __repr__, __len__, __getitem__)
# 6. Repository Pattern (clean architecture)

# ===============

# Day 4: Testing, Tooling & Quality
# Goal: Learn how to write testable, high-quality, production-grade Python code.
# Topics for Day 4:
# pytest basics + fixtures
# Parameterized tests
# Testing with mocks
# Type checking with mypy or pyright
# Code quality tools (ruff, pre-commit)
# Structuring tests properly

# ===============
# Day 5: Async Programming & Concurrency:
# Goal: Understand how to write asynchronous code in Python — one of
# the most powerful features for modern backend and I/O-heavy applications.
# Topics for Day 5:
# Async / Await basics
# asyncio fundamentals (asyncio.run, async def, await)
# TaskGroup (Python 3.11+)
# httpx — Async HTTP client (better than requests)
# When to use Async vs Threading vs Multiprocessing
# Real-world pattern: Async service layer

# ===============
# Day 6: FastAPI & Web APIs
# Goal: Turn your Todo app into a production-ready web API using FastAPI
#  — one of the most popular and modern Python web frameworks in 2026.
# Topics for Day 6:
# FastAPI basics (@app.get, @app.post, Pydantic models)
# Dependency Injection with FastAPI
# Automatic OpenAPI / Swagger docs
# Async endpoints
# Proper project structure for APIs

# ===============
# Day 7: Packaging, Deployment & Production Readiness
# Goal: Learn how to package your FastAPI Todo app so it can be easily installed,
#  deployed, and run in production.
# Topics for Day 7:
# 1. pyproject.toml (modern project metadata)
# 2. uv for dependency management & packaging
# 3. Building distributable packages (uv build)
# 4. Docker basics for containerization
# 5. Running with Uvicorn + Gunicorn (production server)

# ===============
# Day 8: Authentication, Database & Production Features#
# Goal: Add real backend features — User authentication, persistent database,
# and production readiness.
# Topics for Day 8:
# 1. SQLAlchemy + Alembic (Database migrations) ??
# 2. FastAPI Users / JWT Authentication
# 3. Environment variables & .env

# ===============
# Day 9 Plan: Advanced Features & Testing
# User Registration & User Model in DB
# Advanced Error Handling + Global Exception Handler
# CORS
# Basic Logging
# Rate Limiting (using slowapi)
# Basic Token Blacklisting / Logout ??
# Testing (pytest, mocking, integration tests)
# ----
# Learn how to test FastAPI applications
# Unit tests for service layer
# Integration tests for API endpoints
# Mocking dependencies (especially database and auth)
# Test database setup
# Running tests with uv
# ===============

# Day 10: Production Docker & Deployment
# Production-ready Dockerfile
# docker-compose.yml for local development
# Environment management (.env + .dockerignore)
# Health check endpoint + proper startup
# PostgreSQL support (optional)
# Best practices for uv in Docker

# ===============
# Day 11: CI/CD with GitHub Actions
# Automate building, testing, and deployment.
# GitHub Actions Workflow for:
# Running tests on every push
# Building Docker image
# (Optional) Deploy to Render / Railway
#
# Basic CI Pipeline

# ===============
# Day 12: Multithreading & Concurrency
# We'll cover:
#
# Python GIL (Global Interpreter Lock)
# Threading
# Asyncio (we already did some)
# Multiprocessing

# ===============
# Day 13 Goals:
#
# Refresh Tokens
# Long-lived tokens for getting new access tokens
# Better security (short-lived access tokens)
#
# Role-based Access Control
# User roles (admin, user, etc.)
# Protected endpoints based on roles
#
# Logout Mechanism
# Token blacklisting
# Secure logout

# ===============
