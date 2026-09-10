"""
Domain-event consumer.

Reads what the outbox publisher wrote to Kafka and runs side effects
(welcome email, search index, analytics). The API already committed
the user/task — this process must not re-create that row.

At-least-once:
  handle → then commit offset.
  Crash between those two steps redelivers.
  Dedup on processed_events.event_id.

Run (publisher stays in another terminal):

    PYTHONPATH=. uv run python -m workers.event_consumer
"""

from __future__ import annotations

import asyncio
import json
import logging
import signal
from typing import Any

from aiokafka import AIOKafkaConsumer
from sqlalchemy.exc import IntegrityError

from todo.config import settings
from todo.database import SessionLocal
from todo.logging_config import setup_logging
from todo.models import ProcessedEvent

setup_logging()
logger = logging.getLogger(__name__)

# Topology — required. Missing env must fail at startup, not talk to localhost.
BOOTSTRAP = settings.KAFKA_BOOTSTRAP_SERVERS
TOPIC_USERS = settings.KAFKA_TOPIC_USERS
TOPIC_TASKS = settings.KAFKA_TOPIC_TASKS
GROUP_ID = settings.KAFKA_CONSUMER_GROUP

TOPICS = (TOPIC_USERS, TOPIC_TASKS)

COMMIT_EVERY = settings.KAFKA_COMMIT_EVERY  # records
COMMIT_INTERVAL = settings.KAFKA_COMMIT_INTERVAL_SEC  # seconds


def already_processed(event_id: str) -> bool:
    db = SessionLocal()
    try:
        return (
                db.query(ProcessedEvent)
                .where(ProcessedEvent.event_id == event_id)
                .first()
                is not None  # True if a row was found, False if not
        )
    # OR: return db.get(ProcessedEvent, event_id) is not None # shorter, same result
    finally:
        db.close()


def mark_processed(event_id: str, event_type: str, topic: str) -> None:
    db = SessionLocal()
    try:
        db.add(ProcessedEvent(
            event_id=event_id,
            event_type=event_type,
            topic=topic
        ))
        db.commit()
    except IntegrityError:
        db.rollback()  # duplicate - safe to treat as done, do not raise (otherwise same event_id retries forever)
    except Exception:
        db.rollback()
        raise  # db down, constraint etc. - do NOT swallow
    finally:
        db.close()


async def handle_user_registered(payload: dict[str, Any]) -> None:
    """Side effect only. User row already exists from /register."""
    logger.info("user.registered applied user_id=%s username=%s email=%s",
                payload.get("user_id"),
                payload.get("username"),
                payload.get("email"))


async def handle_task_created(payload: dict[str, Any]) -> None:
    logger.info(
        "task.created applied task_id=%s user_id=%s title=%s",
        payload.get("task_id"),
        payload.get("user_id"),
        payload.get("title"),
    )


async def handle_task_completed(payload: dict[str, Any]) -> None:
    logger.info(
        "task.completed applied task_id=%s user_id=%s",
        payload.get("task_id"),
        payload.get("user_id"),
    )


# handler registry / dispatch table
HANDLERS = {
    "user.registered": handle_user_registered,  # map to function, execution happens only when called
    "task.created": handle_task_created,
    "task.completed": handle_task_completed
}


def _header_str(headers: list | None, name: str) -> str | None:
    if not headers:
        return None

    # build a bytes version of name too
    key = name.encode("utf-8") if isinstance(name, str) else name
    for k, v in headers:
        if k == name or k == key:  # compare key as str or byte (just in case kafka may store either)
            return None if v is None else v.decode("utf-8")
    return None


async def handle_message(msg) -> None:
    """
    Decode → idempotent handle → caller commits offset.

    Bad JSON / missing event_id (Kafka UI produce) is skipped so it
    does not stall the partition. Real prod often ships those to a DLT.
    """
    topic = msg.topic
    raw = msg.value

    if not raw:
        logger.warning("Empty payload topic=%s offset=%s - skip", topic, msg.offset)
        return

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.warning(
            "Invalid JSON topic=%s offset=%s err=%s - skip",
            topic,
            msg.offset,
            exc
        )
        return

    if not isinstance(payload, dict):
        logger.warning("Non-object payload topic=%s offset=%s — skip", topic, msg.offset)
        return

    # if payload value is falsy, fall back to the header
    event_type = payload.get("event_type") or _header_str(msg.headers, "event_type")
    event_id = payload.get("event_id") or _header_str(msg.headers, "event_id")

    if not event_type or not event_id:
        logger.warning("Missing event_type/event_id topic=%s offset=%s — skip",
                       topic,
                       msg.offset)
        return

    if already_processed(event_id):
        logger.info("Duplicate event_id=%s type=%s - skip", event_id, event_type)
        return

    handler = HANDLERS.get(event_type)
    if handler is None:
        logger.warning("No handler event_type=%s event_id=%s - skip", event_type, event_id)
        return

    await handler(payload)  # handler function executes here
    mark_processed(str(event_id), str(event_type), topic)
    # any errors bubble to run_consumer()


async def run_consumer() -> None:
    """
    Long-running Kafka consumer.

    Offsets live on the broker (__consumer_offsets), one integer per
    (group, topic, partition). We commit that cursor AFTER a successful
    handle — either every N records, every T seconds, or on shutdown.
    """
    # Client for this process. group_id = who we share work/offsets with.
    consumer = AIOKafkaConsumer(
        *TOPICS,  # topics this worker reads
        bootstrap_servers=BOOTSTRAP,  # broker address
        group_id=GROUP_ID,  # shared cursor + partition assignment
        auto_offset_reset="earliest",  # first run only: start at offset 0
        enable_auto_commit=False,  # we decide when the cursor moves
        session_timeout_ms=30_000,  # broker drops us if we miss heartbeats this long
        heartbeat_interval_ms=3_000,  # keep the group membership alive
        max_poll_records=100,  # max records per internal fetch (not commit size)
    )
    await consumer.start()  # join the group, restore committed offsets
    logger.info(
        "Event consumer started -> %s group=%s topics=%s",
        BOOTSTRAP,
        GROUP_ID,
        ",".join(TOPICS)
    )

    pending = 0  # handled since last commit (not yet flushed)
    last_commit = asyncio.get_event_loop().time()

    async def flush() -> None:
        """Write current positions to __consumer_offsets. No-op if nothing pending."""
        nonlocal pending, last_commit
        if pending == 0:
            return  # nothing new to ack
        await consumer.commit()  # cursor = last handled offset + 1 (all assigned partitions)
        logger.debug("Committed offsets after %s records", pending)
        pending = 0
        last_commit = asyncio.get_event_loop().time()

    try:
        # fetch next record from partitions; wait if topic is idle
        async for msg in consumer:
            try:
                await handle_message(msg)  # parse → inbox check → side effect → mark processed
            except Exception:
                logger.exception(
                    "Handler failed topic=%s offset=%s - not committing batch",
                    msg.topic,
                    msg.offset
                )
                # DO NOT flush. Uncommitted offsets (including this one) will be retried.
                await asyncio.sleep(1)
                continue

            pending += 1  # marking safe to include in next commit
            now = asyncio.get_event_loop().time()
            if pending >= COMMIT_EVERY or (now - last_commit) >= COMMIT_INTERVAL:
                await flush()  # batch ack: one offset write for N successes

    finally:
        try:
            await flush()  # shutdown: ack the leftover 1..N-1 records
        finally:
            await consumer.stop()  # leave the group; always run even if flush fails
        logger.info("Event consumer stopped")


def main() -> None:
    """
    Run the Kafka consumer on a dedicated event loop.

    Same lifecycle as asyncio.run(run_consumer()): create a loop, attach it
    to this thread, queue the consumer, block until it finishes, then shut
    down async generators, and close the loop.

    Extra vs asyncio.run(): handle SIGINT and SIGTERM so Docker/k8s stop
    cancels the task and run_consumer() can flush offsets and leave the group.
    """

    # create an event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    # Schedule the consumer; it starts when run_until_complete runs
    task = loop.create_task(run_consumer())

    def _stop() -> None:
        task.cancel()  # shutdown → run_consumer() finally (flush + stop)

    # register OS signals - SIGINT and SIGTERM with the process
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop)
        except NotImplementedError:
            signal.signal(sig, lambda *_: _stop())  # handling for Windows OS

    try:
        loop.run_until_complete(task)  # block this thread until consumer ends
    except asyncio.CancelledError:
        pass  # expected after _stop(); don't dump a traceback
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())  # close leftover async generators
        loop.close()


if __name__ == "__main__":
    main()
