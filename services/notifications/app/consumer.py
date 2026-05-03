"""Pika BlockingConnection consumer. Runs in a daemon thread spawned from
the FastAPI lifespan so the HTTP app and the consumer share one process.

The outer `while True` is intentional: pika raises on broker restarts and
on the brief window between container start and rabbitmq becoming healthy.
We log and reconnect rather than letting the thread die silently."""
from __future__ import annotations

import json
import logging
import os
import threading
import time

import pika
from pika.exceptions import AMQPConnectionError, AMQPError

from shared.events import EXCHANGE_NAME

from . import email as mailer

log = logging.getLogger(__name__)

QUEUE_NAME = "notifications.issue.events"


def _on_issue_event(body: bytes) -> None:
    try:
        evt = json.loads(body)
    except json.JSONDecodeError:
        log.exception("malformed event payload, dropping")
        return

    event_type = evt.get("event")
    issue = evt.get("issue", {})
    tenant_id = evt.get("tenant_id", "unknown")

    if event_type == "issue.created":
        mailer.send(
            to=f"tenant-{tenant_id}@notifications.mjira.local",
            subject=f"[mjira] New issue: {issue.get('title', '(no title)')}",
            body=(
                f"Issue {issue.get('id')} was created in tenant {tenant_id}.\n"
                f"Title: {issue.get('title')}\n"
                f"Project: {issue.get('project_id')}\n"
                f"Created by: {issue.get('created_by')}\n"
            ),
        )
    else:
        log.info("ignoring unhandled event type %s", event_type)


def _consume_once() -> None:
    conn = pika.BlockingConnection(pika.URLParameters(os.environ["RABBITMQ_URL"]))
    ch = conn.channel()
    ch.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="topic", durable=True)
    ch.queue_declare(queue=QUEUE_NAME, durable=True)
    ch.queue_bind(queue=QUEUE_NAME, exchange=EXCHANGE_NAME, routing_key="issue.*")
    ch.basic_qos(prefetch_count=10)

    def on_message(channel, method, properties, body):  # noqa: ANN001
        try:
            _on_issue_event(body)
            channel.basic_ack(method.delivery_tag)
        except Exception:
            log.exception("handler crashed; nacking without requeue")
            channel.basic_nack(method.delivery_tag, requeue=False)

    ch.basic_consume(queue=QUEUE_NAME, on_message_callback=on_message)
    log.info("notifications consumer ready, waiting for events")
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
    t = threading.Thread(target=_run_forever, daemon=True, name="rabbit-consumer")
    t.start()
    return t
