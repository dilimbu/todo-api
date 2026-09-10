"""
PYTHONPATH=. uv run pytest todo/tests/test_event_consumer.py -v --tb=short
"""

import json
import uuid
from types import SimpleNamespace

import pytest

from todo.models import ProcessedEvent
from todo.tests.conftest import TestingSessionLocal
from workers.event_consumer import mark_processed, handle_message


@pytest.fixture(autouse=True)
def _use_test_db(monkeypatch):
    """Worker SessionLocal() must hit SQLite, not Postgres."""
    # point worker consumer to same session factory as the tests
    monkeypatch.setattr(
        "workers.event_consumer.SessionLocal",
        TestingSessionLocal
    )


def _msg(event_id, event_type="task.created", payload=None, headers=True):
    """
    Fake aiokafka ConsumerRecord.

    handle_message only needs topic / offset / value / headers.
    SimpleNamespace is enough — no real Kafka types.
    """
    body = payload or {
        "event_id": event_id,
        "event_type": event_type,
        "task_id": 2,
        "user_id": 2,
        "title": "Test Kafka"
    }
    hdrs = []
    if headers:
        hdrs = [
            ("event_id", event_id.encode()),
            ("event_type", event_type.encode())
        ]
    # SimpleNamespace - tiny object we can stick attributes on
    return SimpleNamespace(
        topic="todo.tasks",
        partition=0,
        offset=1,
        value=json_bytes(body),
        headers=hdrs
    )


def json_bytes(obj) -> bytes:
    return json.dumps(obj).encode()


@pytest.mark.asyncio
async def test_consumer_duplicate_event_id_is_skipped(test_db, monkeypatch):
    """
    Inbox already has this event_id (previous delivery).
    already_processed() must skip the handler entirely.
    """
    event_id = str(uuid.uuid4())
    mark_processed(event_id, "task.created", "todo.tasks")

    calls = {"n": 0}

    async def fake_handler(_payload):
        calls["n"] += 1

    # Swap the real log handler so we can count invocations.
    monkeypatch.setitem(
        __import__("workers.event_consumer", fromlist=["HANDLERS"]).HANDLERS,
        "task.created",
        fake_handler
    )

    await handle_message(_msg(event_id))

    assert calls["n"] == 0
    assert test_db.query(ProcessedEvent).where(ProcessedEvent.event_id == event_id).count() == 1


@pytest.mark.asyncio
async def test_consumer_applies_then_second_delivery_skips(test_db, monkeypatch):
    """
    First message: handler runs once, inbox row inserted.
    Second message with the same event_id: handler must not run again.
    """
    event_id = str(uuid.uuid4())
    calls = {"n": 0}

    async def fake_handler(_payload):
        calls["n"] += 1

    # monkeypatch - fixture that temporarily replaces attribute then puts it back when test ends
    # here it replaces the handle_task_created handler with fake_handler and replaces back
    monkeypatch.setitem(
        __import__("workers.event_consumer", fromlist=["HANDLERS"]).HANDLERS,
        "task.created",
        fake_handler
    )
    # OR, cleaner version:
    # monkeypatch.setitem(workers.event_consumer.HANDLERS, "task.created", fake_handler)

    await handle_message(_msg(event_id))
    await handle_message(_msg(event_id))

    assert calls["n"] == 1
    assert test_db.query(ProcessedEvent).where(ProcessedEvent.event_id == event_id).count() == 1
