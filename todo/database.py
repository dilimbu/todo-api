# standard database setup code for FastAPI + SQLAlchemy

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from todo.config import settings

# ====================== Database Configuration ======================


BASE_DIR = Path(__file__).resolve().parent.parent  # project root

DATABASE_URL = settings.DATABASE_URL

# Create the database engine, the core connection to the db
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)

# SessionLocal creates new database sessions when called
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class that all SQLAlchemy models will inherit from
Base = declarative_base()


# Dependency function for FastAPI
def get_db():
    """FastAPI dependency: one session per request, always closed."""
    db = SessionLocal()
    try:
        yield db  # Give session to the endpoint (session is available during the request)
    finally:  # automatically close after the request is done
        db.close()  # Always close the session after the request

# ============================

# Why this pattern?
#
# Each API request gets its own fresh database session.
# The session is automatically closed after the request.
# Clean separation between database logic and API logic.

# if you usd "return" instead of "yield":
# The session might not be properly closed if an error occurs.
# FastAPI loses control over the lifecycle of the session.
# You could have connection leaks.

# yield makes this function a generator. FastAPI uses it to:
#
# Create the database session before the endpoint runs.
# Pass the db to your endpoint function.
# Keep the session open during the entire request.
# Close the session after the request is finished (in the finally block).
