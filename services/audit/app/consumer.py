"""Audit consumer. Binds `#` (catch-all) to the mjira.events topic exchange
and persists every event idempotently via INSERT ... ON CONFLICT DO NOTHING
on the unique event_id column.

Same daemon-thread + reconnect pattern as notifications-service. See
services/notifications/README.md for the rationale on why we chose this
shape over async or a separate worker process."""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime

import pika
from pika.exceptions import AMQPConnectionError, AMQPError
from sqlalchemy.dialects.postgresql import insert as pg_insert

from shared.events import EXCHANGE_NAME

from .db import SessionLocal
from .models import AuditEvent

log = logging.getLogger(__name__)

QUEUE_NAME = "audit.all"


def _persist(routing_key: str, body: bytes) -> None:
    payload = json.loads(body)
    event_id = payload.get("event_id")
    if not event_id:
        log.warning("event %s has no event_id; skipping (won't dedupe safely)", routing_key)
        return

    occurred_at_raw = payload.get("occurred_at")
    occurred_at = (
        datetime.fromisoformat(occurred_at_raw) if occurred_at_raw else None
    )

    tenant_raw = payload.get("tenant_id")
    tenant_id = uuid.UUID(tenant_raw) if tenant_raw else None

    stmt = pg_insert(AuditEvent).values(
        event_id=uuid.UUID(event_id),
        event_type=routing_key,
        tenant_id=tenant_id,
        payload=payload,
        **({"occurred_at": occurred_at} if occurred_at else {}),
    ).on_conflict_do_nothing(index_elements=["event_id"])

    with SessionLocal() as session:
        session.execute(stmt)
        session.commit()


def _consume_once() -> None:
    conn = pika.BlockingConnection(pika.URLParameters(os.environ["RABBITMQ_URL"]))
    ch = conn.channel()
    ch.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="topic", durable=True)
    ch.queue_declare(queue=QUEUE_NAME, durable=True)
    ch.queue_bind(queue=QUEUE_NAME, exchange=EXCHANGE_NAME, routing_key="#")
    ch.basic_qos(prefetch_count=20)

    def on_message(channel, method, properties, body):  # noqa: ANN001
        try:
            _persist(method.routing_key, body)
            channel.basic_ack(method.delivery_tag)
        except Exception:
            log.exception("audit handler crashed; nacking without requeue")
            channel.basic_nack(method.delivery_tag, requeue=False)

    ch.basic_consume(queue=QUEUE_NAME, on_message_callback=on_message)
    log.info("audit consumer ready, waiting for events")
    ch.start_consuming()


def _run_forever() -> None:
    while True:
        try:
            _consume_once()
        except AMQPConnectionError as exc:
            log.warning("rabbitmq not reachable (%s); retrying in 3s", exc)
            time.sleep(3)
        except AMQPError:
            log.exception("amqp error; reconnecting in 3s")
            time.sleep(3)


def start_in_background() -> threading.Thread:
    t = threading.Thread(target=_run_forever, daemon=True, name="audit-consumer")
    t.start()
    return t
