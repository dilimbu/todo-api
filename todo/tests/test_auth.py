"""
Test file for Authentication endpoints (Registration & Login)
"""

"""
To run tests:
From the project root (day8-secure-todo/):
-v = verbose, shows more detailed output for each test

uv run pytest todo/tests/ -v

or for a specific file:
-tb=short , tb = traceback, so, short traceback

uv run pytest todo/tests/test_auth.py -v --tb=short

"""

from fastapi.testclient import TestClient


def test_register_user(client: TestClient):
    """Test successful user registration"""
    user_data = {
        "username": "testuser",
        "password": "testpassword123",
        "email": "test@example.com"
    }
    response = client.post("/register", json=user_data)

    assert response.status_code == 201
    data = response.json()
    assert data["username"] == user_data["username"]
    assert "id" in data
    assert data["is_active"] is True


# NOTE: registered_user is a fixture that gets called from conftest.py
# runs the fixture and passes the return of it as registered_user parameter
# to this test. Also no import needed
def test_register_duplicate_user(client: TestClient, registered_user):
    """Test that duplicate username registration fails"""

    # NOTE: First registration already called when registered_user fixture is called
    # so when you call this, it's duplicate call to /register
    response = client.post("/register", json=registered_user)

    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]


def test_login_success(client: TestClient, registered_user):
    """Test successful login and token return"""
    # user is already registered vis fixture registered_user
    response = client.post(
        "/login",
        data={
            "username": registered_user["username"],
            "password": registered_user["password"]
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_invalid_credentials(client: TestClient):
    """Test login with wrong credentials"""
    response = client.post(
        "/login",
        data={"username": "wronguser", "password": "wrongpassword"},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )

    assert response.status_code == 401
    assert "Incorrect username or password" in response.json()["detail"]


def test_protected_endpoint_without_token(client: TestClient):
    """Test that protected endpoints require authentication"""
    response = client.get("/tasks")
    assert response.status_code == 401


# ====================== Testing jobs ======================

from unittest.mock import AsyncMock, MagicMock
from pytest_mock import MockerFixture


def test_register_enqueues_welcome_job(client: TestClient, mock_arq_create_pool) -> None:
    """Register should enqueue ARQ job welcome_user with the username."""

    # We fake Redis queue in conftest -> mock_arq_create_pool, so not needed below:

    # # fake Redis/ARQ pool object
    # mock_pool = MagicMock()
    # # fake async method so await enqueue_job(..) works and we can use assert_awaited_once_with
    # mock_pool.enqueue_job = AsyncMock()  # attach enqueue_job attribute
    #
    # # Patch the pool used by main2. Replaces main2.redis_pool with mock_pool for this test only
    # # Path must match where the name is looked up: from main2 import redis_pool / main2.redis_pool
    # # in the register handler. After the test, pytest-mock undoes the patch
    #
    # mocker.patch("main2.redis_pool", mock_pool)

    # Real HTTP call through app and hit's the register route (DB is the test DB from conftest)
    response = client.post(
        "/register",
        json={
            "username": "queueuser1",
            "email": "queue1@example.com",
            "password": "password123"
        }
    )

    assert response.status_code == 201
    # test enqueue_job was awaited exactly once, if register never enqueues or uses
    # another name / tags, this fails
    mock_arq_create_pool.enqueue_job.assert_awaited_once_with("welcome_user", "queueuser1")

    # NOTE: This test only proves: register tried to enqueue the right job with the right username.
    # It does not prove Redis is running, if worker processed the job or the welcome_user function
    # exists on the worker, Those need integration tests

    # Flow:
    # pytest
    #   → builds client (test DB)
    #   → builds mocker
    #   → runs test
    #        patch redis_pool → mock
    #        POST /register
    # redis_pool is mock_pool → calls mock_pool.enqueue_job(...)
    #        assert 201
    #        assert mock got enqueue_job("welcome_user", "queueuser1")

    # To run just this test:
    # PYTHONPATH=. uv run pytest todo/tests/test_auth.py::test_register_enqueues_welcome_job -v

# ==============================================================
# Test Coverage Report:

# A coverage report tells you how much of your code is actually being tested by your test suite.
# It shows:
#
# Which lines of code are executed during tests
# Which lines are not tested (missed)
# Percentage of code covered
#
#
# Why is it useful?
#
# Helps find untested parts of your code
# Encourages better testing
# Gives you confidence in your test suite
# Often required in professional projects

# Step 1: Add to pyproject.toml
# Add this:
# toml"pytest-cov>=5.0.0",
# Then run:
# Bashuv sync
#
# Step 2: Run Coverage
# From project root:
# BashPYTHONPATH=. uv run pytest todo/tests --cov=todo --cov-report=term-missing -v


# Name                         Stmts   Miss  Cover   Missing
# ----------------------------------------------------------
# todo/__init__.py                 0      0   100%
# todo/auth2.py                   45      5    89%   32-33, 77-79
# todo/auth.py                    37     37     0%   37-144
# todo/config.py                   8      0   100%
# todo/crud.py                    25     25     0%   1-40
# todo/database.py                13      4    69%   33-37
# todo/dependencies.py            11      2    82%   37-38
# todo/exceptions.py              15      4    73%   14-15, 33-34
# todo/logging_config.py           8      0   100%
# todo/models.py                  17      0   100%
# todo/rate_limiter.py             5      1    80%   15
# todo/schemas.py                 22      0   100%
# todo/service.py                 32      0   100%
# todo/tests/conftest.py          39      0   100%
# todo/tests/test_api.py          22      0   100%
# todo/tests/test_auth.py         28      0   100%
# todo/tests/test_service.py      62      0   100%
# ----------------------------------------------------------
# TOTAL                          389     78    80%

# Example Report:
# BashName                    Stmts   Miss  Cover   Missing
# -----------------------------------------------------
# todo/main.py               92      8    91%   45-52, 78
# todo/service.py            38      2    95%   67
# todo/auth.py               55      5    91%   23, 41-44
# todo/models.py             12      0   100%
# todo/schemas.py            25      0   100%
# Column Explanation:
#
# Stmts — Total number of executable statements (lines of code)
# Miss — Number of statements not executed by tests
# Cover — Percentage of code covered by tests (higher is better)
# Missing — Line numbers that are not tested
#
#
# How to Read It:
#
# 100% → Perfectly tested
# 90%+ → Very good
# 70-89% → Acceptable for most projects
# Below 70% → Needs more tests
#
# Missing lines tell you exactly where to add more tests.
