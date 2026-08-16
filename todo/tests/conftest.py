from pathlib import Path
import sys

from todo.rate_limiter import limiter

# Add project root to Python path (important for imports)
# NOTE: this needs to be added (before any imports)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient  # simulates HTTP requests to FastAPI without running real server

from main2 import app
from todo.database import Base, get_db

# Test database setup
TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
# SQLLite by default allows only one thread to access the database at a time
# setting it to "false" allows multiple threads to use the same database connection

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def test_db():
    """Create fresh test database and tables for each test"""

    # Create tables (all the model classes are automatically registered with Base.metadata)
    # SQLAlchemy looks all classes inherited from Base and generates CREATE TABLE statement
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db  # Give test the DB session
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)  # Close up after test


@pytest.fixture(scope="function")
def client(test_db):
    """Test client with overridden DB dependency"""

    def override_get_db():
        try:
            yield test_db
        finally:
            test_db.close()

    app.dependency_overrides[get_db] = override_get_db  # overriding normal get_db() dependency with test db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()  # clear override


# Fixture: Creates fresh tables before each test
# Provides a database session to the test
# Cleans everything up after the test finishes
# It overrides your normal get_db() dependency with the test database.
# Gives you a TestClient you can use to make real-looking API calls in tests.

# What is a fixture in pytest?
# A fixture is a reusable piece of setup/teardown code that pytest runs automatically before (and after) your tests.
# Think of it as "test preparation code" that can be shared across multiple tests.

# ====================== User Fixtures ======================
@pytest.fixture(scope="function")
def registered_user(client: TestClient):
    """Create a registered test user"""
    user_data = {
        "username": "testuser",
        "password": "testpassword123",
        "email": "test@example.com"
    }
    client.post("/register", json=user_data)
    return user_data


# registered_user fixture runs -> creates user and passes this
# as registered_user parameter to the auth_token()
@pytest.fixture(scope="function")
def auth_token(client: TestClient, registered_user):
    """Return valid JWT token for authenticated requests"""
    response = client.post(
        "/login",
        data={
            "username": registered_user["username"],
            "password": registered_user["password"]
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    return response.json()["access_token"]


# autouse=True -> this fixture will run automatically for every test in the test suite.
@pytest.fixture(autouse=True)
def disable_rate_limiting():
    """Disable rate limiting during tests"""
    original = limiter.enabled
    limiter.enabled = False  # ← Runs BEFORE each test
    yield  # ← Test runs here
    limiter.enabled = original  # restoring original state, # ← Runs AFTER each test


from unittest.mock import AsyncMock, MagicMock

import pytest

# Separate Redis for test / For real redis docker - integration test only
@pytest.fixture(autouse=True)
def mock_arq_create_pool(mocker):
    """
    Avoid real Redis during tests.
    lifespan calls create_pool() on startup — return a fake pool immediately.
    """
    mock_pool = MagicMock()
    mock_pool.enqueue_job = AsyncMock()
    mock_pool.close = AsyncMock()  # lifespan may await redis_pool.close()

    async def fake_create_pool(*args, **kwargs):
        return mock_pool

    # Patch where main2 looks up the name
    mocker.patch("main2.create_pool", side_effect=fake_create_pool)
    mocker.patch("main2.redis_pool", mock_pool)

    return mock_pool
