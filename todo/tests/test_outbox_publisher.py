"""
PYTHONPATH=. uv run pytest todo/tests/test_outbox_publisher.py
"""

import uuid
from unittest.mock import MagicMock, AsyncMock

import pytest

from todo.models import OutboxEvent
from workers.outbox_publisher import publish_batch, MAX_ATTEMPTS


def _outbox(db, attempts=0, status="pending"):
    event_id = str(uuid.uuid4())
    row = OutboxEvent(
        event_id=event_id,
        event_type="task.created",
        aggregate_type="task",
        aggregate_id="2",
        topic="todo.tasks",
        payload={"event_id": event_id, "event_type": "task.created", "task_id": 2, "user_id": 2, "title": "Test kafka"},
        status=status,
        attempts=attempts
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.mark.asyncio
async def test_publish_batch_marks_published_after_ack(test_db):
    """send_and_wait returns → row becomes published and published_at is set."""
    row = _outbox(test_db)
    producer = MagicMock()
    # await producer.send_and_wait(...) succeeds
    producer.send_and_wait = AsyncMock(return_value=None)

    await publish_batch(producer, test_db, [row])

    test_db.refresh(row)  # reload columns after publisher commit
    assert row.status == "published"
    assert row.published_at is not None
    producer.send_and_wait.assert_awaited_once()


@pytest.mark.asyncio
async def test_publish_batch_stays_pending_on_broker_error(test_db):
    """Broker error → stay pending, bump attempts, store last_error. Retry later."""
    row = _outbox(test_db)
    producer = MagicMock()
    producer.send_and_wait = AsyncMock(side_effect=RuntimeError("broken down"))

    await publish_batch(producer, test_db, [row])

    test_db.refresh(row)
    assert row.status == "pending"
    assert row.attempts == 1
    assert row.last_error


@pytest.mark.asyncio
async def test_publish_batch_fails_at_max_attempts(test_db):
    """Last allowed failure → status=failed so the publisher stops picking it up."""
    # Already one short of the cap; this failure should trip MAX_ATTEMPTS.
    row = _outbox(test_db, attempts=MAX_ATTEMPTS - 1)
    producer = MagicMock()
    producer.send_and_wait = AsyncMock(side_effect=RuntimeError("broker down"))

    await publish_batch(producer, test_db, [row])

    test_db.refresh(row)
    assert row.status == "failed"
    assert row.attempts == MAX_ATTEMPTS
