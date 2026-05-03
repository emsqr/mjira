"""Sync RabbitMQ publisher used by services to emit domain events.

Topology: a single durable topic exchange `mjira.events`. Routing keys are
dotted strings like `issue.created`, `issue.updated`. Each consumer service
declares its own queue and binds with whatever pattern it cares about
(e.g. `issue.*`, `#`).

Connection-per-publish is intentional. It costs ~1-5ms over the local docker
network and removes every thread-safety question that comes with sharing a
pika BlockingConnection across FastAPI's thread pool. Production would use
a connection pool — see `# TODO(phase 2.5)` callsites.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import UTC, datetime
from typing import Any

import pika

EXCHANGE_NAME = "mjira.events"

log = logging.getLogger(__name__)


def publish_event(routing_key: str, payload: dict[str, Any]) -> None:
    """Publish one event. Failures are logged, not raised — a notification
    miss must never break the user-facing write that produced it.

    The publisher injects `event_id` (uuid) and `occurred_at` (iso8601 utc)
    into the payload so consumers can dedupe under at-least-once delivery
    without each call site remembering to add them.
    """
    payload = {
        "event_id": str(uuid.uuid4()),
        "occurred_at": datetime.now(UTC).isoformat(),
        **payload,
    }
    body = json.dumps(payload, default=str).encode()
    try:
        params = pika.URLParameters(os.environ["RABBITMQ_URL"])
        params.socket_timeout = 3
        with pika.BlockingConnection(params) as conn:
            ch = conn.channel()
            ch.exchange_declare(
                exchange=EXCHANGE_NAME, exchange_type="topic", durable=True
            )
            ch.basic_publish(
                exchange=EXCHANGE_NAME,
                routing_key=routing_key,
                body=body,
                properties=pika.BasicProperties(
                    content_type="application/json",
                    delivery_mode=2,  # persistent
                    message_id=payload["event_id"],
                ),
            )
    except Exception:
        log.exception("failed to publish event %s", routing_key)
