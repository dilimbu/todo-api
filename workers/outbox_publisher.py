"""
Transactional outbox publisher worker (batch).

Reads pending rows from the outbox table and publishes them to Kafka.
Safe to stop anytime: unsent rows stay pending and are picked up on restart.

Flow:
  1. Fetch a batch of pending outbox rows from the DB
  2. Publish each event to Kafka
  3. Update status / attempts in memory
  4. Single db.commit() for the whole batch

At-least-once: if we crash after Kafka ack but before commit, the row stays
pending and may be published again. Consumers must be idempotent (event_id).

Run:
  PYTHONPATH=. uv run python -m workers.outbox_publisher
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from aiokafka import AIOKafkaProducer
from sqlalchemy.orm import Session

from todo.config import settings
from todo.database import SessionLocal
from todo.logging_config import setup_logging
from todo.models import OutboxEvent

logger = logging.getLogger(__name__)

BATCH_SIZE = int(getattr(settings, "OUTBOX_BATCH_SIZE", 50))  # rows per poll (keep transactions modest)
POLL_SECONDS = float(getattr(settings, "OUTBOX_POLL_SECONDS", 1.0))  # idle sleep between polls
MAX_ATTEMPTS = int(getattr(settings, "OUTBOX_MAX_ATTEMPTS", 8))  # after this, mark failed and stop retrying


def fetch_pending(db: Session) -> list[OutboxEvent]:
    """
    Load a batch of events that still need to be sent.

    Only status == 'pending'. Oldest first so events roughly preserve order.

    NOTE: For Production (PostgreSQL, multiple publisher replicas):
      add .with_for_update(skip_locked=True)
    so two workers don't claim the same rows.
    SQLite does not support SKIP LOCKED the same way — fine for local single worker.
    """
    query = (
        db.query(OutboxEvent)
        .where(OutboxEvent.status == "pending")
        .order_by(OutboxEvent.created_at.asc())
        .limit(BATCH_SIZE)
    )
    # Uncomment when on Postgres, MySQL, with more than one publisher:
    # query = query.with_for_update(skip_locked=True)   # if another worker already locked rows, skip and select other free ones

    return query.all()


async def publish_batch(producer: AIOKafkaProducer, db: Session, events: list[OutboxEvent]) -> None:
    """
    Publish all events in the batch, then commit DB once.

    Success → status = published, published_at set, last_error cleared
    failure → attempts += 1, last_error set
              status stays pending until MAX_ATTEMPTS, then failed
    """
    if not events:
        return

    for event in events:
        try:
            # Key helps Kafka partition by aggregate (e.g. all events for user 8 together)
            key = f"{event.aggregate_type}:{event.aggregate_id}".encode("utf-8")  # utf-8 converts to byte eg. b"user:8"
            body = json.dumps(event.payload).encode("utf-8")

            headers = [
                ("event_id", event.event_id.encode("utf-8")),
                ("event_type", event.event_type.encode("utf-8"))
            ]
            # Wait for broker ack so we only mark published after Kafka accepted it
            await producer.send_and_wait(event.topic, key=key, value=body, headers=headers)

            event.status = "published"
            event.published_at = datetime.now(timezone.utc)
            event.last_error = None

            logger.info(
                "Published event_id=%s type=%s topic=%s",
                event.event_id,
                event.event_type,
                event.topic
            )
        except Exception as exc:
            # Do not re-raise — one bad event should not block the rest of the batch
            event.attempts = (event.attempts or 0) + 1
            event.last_error = str(exc)[:2000]

            if event.attempts >= MAX_ATTEMPTS:
                event.status = "failed"
                logger.exception(
                    "Giving up event_id=%s after %s attempts",
                    event.event_id,
                    event.attempts
                )
            else:
                # leave status=pending for next poll
                event.status = "pending"
                logger.exception(
                    "Publish failed event_id=%s attempts=%s - will retry",
                    event.event_id,
                    event.attempts
                )
    # One DB round-trip for the whole batch
    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to commit outbox batch of %s events", len(events))
        raise


async def run_loop(producer: AIOKafkaProducer) -> None:
    """Poll forever: short-lived session per poll, batch publish, sleep."""
    while True:
        # New session each poll: avoid long-lived sessions / stale state
        db = SessionLocal()
        try:
            events = fetch_pending(db)
            if events:
                logger.debug("Fetched %s pending outbox events", len(events))
                await publish_batch(producer, db, events)
        except Exception:
            logger.exception("Publisher loop iteration failed")
            try:
                db.rollback()
            except Exception:
                pass
        finally:
            db.close()

        await asyncio.sleep(POLL_SECONDS)


async def main() -> None:
    """Process entrypoint."""
    setup_logging()

    if not settings.KAFKA_ENABLED:
        logger.error("KAFKA_ENABLED=false - outbox publisher exiting")
        return

    bootstrap = settings.KAFKA_BOOTSTRAP_SERVERS
    producer = AIOKafkaProducer(
        bootstrap_servers=bootstrap,
        enable_idempotence=True,
        linger_ms=10,
        compression_type="gzip"
    )

    await producer.start()
    logger.info("Outbox publisher started -> %s (batch_size=%s)", bootstrap, BATCH_SIZE)

    try:
        await run_loop(producer)
    finally:
        await producer.stop()
        logger.info("Outbox publisher stopped")


if __name__ == "__main__":
    asyncio.run(main())
