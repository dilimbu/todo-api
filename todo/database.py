# standard database setup code for FastAPI + SQLAlchemy

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from pathlib import Path

# ====================== Database Configuration ======================
# Tells SQLAlchemy where the database is.
# SQLite database file will be created in the project root

BASE_DIR = Path(__file__).resolve().parent.parent # project root
DATABASE_URL = f"sqlite:///{BASE_DIR}/tasks.db"

# Create the database engine, the core connection to the db
# connect_args is required for SQLite when using with FastAPI
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False})  # Required for SQLite with FastAPI
# SQLLite by default allows only one thread to access the database at a time
# setting it to "false" allows multiple threads to use the same database connection
# FastAPI uses multiple threads (via UVIcorn workers) to handle concurrent requests

# SessionLocal creates new database sessions when called
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class that all SQLAlchemy models will inherit from
Base = declarative_base()


# Dependency function for FastAPI
# This creates a new database session for each request and closes it after use
def get_db():
    db = SessionLocal()
    try:
        yield db  # Give session to the endpoint (session is available during the request)
    finally:  # automatically close after the request is done
        db.close()  # Always close the session after the request

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


# ============================

