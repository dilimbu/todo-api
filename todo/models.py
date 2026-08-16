from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


# SQLAlchemy model or ORM model (maps to database table) - represents the 'tasks' table in the database
class Task(Base):
    __tablename__ = "tasks"  # name of table in db. SqlAlchemy's special attribute

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)  # Indexed for faster searches
    done = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())  # function generator, Auto timestamp

    # OWNERSHIP: required FK to users
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    owner = relationship("User", back_populates="tasks")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=True)
    is_active = Column(Boolean, default=True)
    role = Column(String, default="User")  # "user", "admin"
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # One user → many tasks
    tasks = relationship(
        "Task",
        back_populates="owner",
        cascade="all, delete-orphan"  # deleting user removes their tasks
    )


class TokenBlacklist(Base):
    __tablename__ = "token_blacklist"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime,
                        default=lambda: datetime.now(timezone.utc))  # in prod - server_default=func.now() is better

# CREATE TABLE IF NOT EXISTS tasks (
# 	id INTEGER PRIMARY KEY AUTOINCREMENT,
# 	title TEXT NOT NULL,
# 	done BOOLEAN DEFAULT 0,
# 	created_at DATETIME DEFAULT CURRENT_TIMESTAMP
# );


# -- Create the table
# CREATE TABLE IF NOT EXISTS users (
#     id INTEGER PRIMARY KEY AUTOINCREMENT,
#     username TEXT UNIQUE NOT NULL,
#     hashed_password TEXT NOT NULL,
#     email TEXT UNIQUE,
#     is_active INTEGER DEFAULT 1,
#     created_at TEXT DEFAULT CURRENT_TIMESTAMP
# );
#
# -- Create indexes (recommended)
# CREATE INDEX IF NOT EXISTS idx_users_username ON users (username);
# CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);

# What is Alembic:
#
# Alembic is a database migration tool for SQLAlchemy.
#
# You define your models in models.py (using SQLAlchemy)
# You run:Bashalembic revision --autogenerate -m "add token_blacklist"
# Alembic compares your models with the current database
# It automatically generates a migration script (Python file)
# You run:Bashalembic upgrade head
# Alembic applies the changes → creates/alters tables
# Alembic knows your database through the alembic.ini file and the env.py file.

# First install alembic, (make sure it's in pyproject.toml file, and uv sync)
# Then, initialize it:
# uv run alembic init alembic
# This will create:
#
# alembic.ini
# alembic/ folder

# Then update alembic.ini with your db:
# sqlalchemy.url = sqlite:///./tasks.db

# and also: alembic/env.py to add database and models (make sure all models are imported)


# Run in terminal:
# uv run alembic revision --autogenerate -m "add token_blacklist table"
# uv run alembic upgrade head
