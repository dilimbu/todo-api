"""Transactional outbox — write events in the SAME DB session as business data."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from todo.config import settings
from todo.models import OutboxEvent


# this is a thin layer, and clean design, exception bubbles if db fails, and transaction rolls back
# so no need for adding exception handling here

def enqueue_event(
        db: Session,  # directly calling db, no Depends(), that's for FastAPI
        *,  # ← everything after this must be passed by keyword
        event_type: str,
        aggregate_type: str,
        aggregate_id: str | int,
        topic: str,
        payload: dict[str, Any]  # dictionary with string keys and values of any type
) -> OutboxEvent:
    """
    Stage an event. Caller MUST commit the session.
    Do NOT publish to Kafka here — that is the publisher worker's job.
    """
    event_id = str(uuid.uuid4())
    event = OutboxEvent(
        event_id=event_id,
        event_type=event_type,
        aggregate_type=aggregate_type,
        aggregate_id=str(aggregate_id),
        topic=topic,
        payload={
            **payload,
            "event_id": event_id,
            "event_type": event_type,
            "occurred_at": datetime.now(timezone.utc).isoformat()
        },
        status="pending"
    )
    db.add(event)
    # note: no db.commit() here, that will be in business change and will be in same commit (so both or neither)
    return event


def enqueue_user_registered(db: Session, user) -> OutboxEvent:
    return enqueue_event(
        db,
        event_type="user.registered",
        aggregate_type="user",
        aggregate_id=user.id,
        topic=settings.KAFKA_TOPIC_USERS,
        payload={
            "user_id": user.id,
            "username": user.username,
            "email": getattr(user, "email", None)
        }
    )


def enqueue_task_created(db: Session, task, user_id: int) -> OutboxEvent:
    return enqueue_event(
        db,
        event_type="task.created",
        aggregate_type="task",
        aggregate_id=task.id,
        topic=settings.KAFKA_TOPIC_TASKS,
        payload={
            "task_id": task.id,
            "user_id": user_id,
            "title": task.title,
        }
    )


def enqueue_task_completed(db: Session, task, user_id: int) -> OutboxEvent:
    return enqueue_event(
        db,
        event_type="task.complete",
        aggregate_type="task",
        aggregate_id=task.id,
        topic=settings.KAFKA_TOPIC_TASKS,
        payload={
            "task_id": task.id,
            "user_id": user_id,
        },
    )
