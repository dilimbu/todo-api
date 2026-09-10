from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON, Text
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


class OutboxEvent(Base):
    __tablename__ = "outbox"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(36), unique=True, nullable=False, index=True)  # UUID str
    event_type = Column(String(64), nullable=False, index=True)  # e.g. user.registered, task.created
    aggregate_type = Column(String(32), nullable=False)  # user | task
    aggregate_id = Column(String(64), nullable=False, index=True)
    topic = Column(String(128), nullable=False)
    payload = Column(JSON, nullable=False)
    status = Column(
        String(16),
        nullable=False,
        default="pending",  # used when create objects in Python
        server_default="pending",  # used by database if a row is inserted without status
        index=True)  # pending|published|failed
    attempts = Column(Integer, nullable=False, default=0, server_default="0")
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    published_at = Column(DateTime(timezone=True), nullable=True)


class ProcessedEvent(Base):
    """Inbox: event_id already applied by a consumer. Idempotency store."""
    __tablename__ = "processed_events"

    event_id = Column(String(36), primary_key=True)
    event_type = Column(String(100), nullable=False)
    topic = Column(String(200), nullable=False)
    processed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
