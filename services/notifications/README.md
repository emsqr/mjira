# notifications-service

A consumer-only microservice that listens for domain events on a RabbitMQ
exchange and turns them into emails. This is the first service in the
project that talks to other services **asynchronously** — the others all
communicate over HTTP, where the caller blocks until the callee replies.

## Why a separate service for this?

When you create an issue, the user shouldn't wait for an email to be sent
before getting their HTTP 201 back. More importantly, the issues service
shouldn't need to know *anything* about how notifications work — what
SMTP server we use, what the email template looks like, who to notify. If
a future product person asks "can we also send a Slack message?", that
should be a change in one place, not in the issues service.

The classic decoupling pattern: **issues publishes a fact** (`issue.created`)
to a broker; **anyone interested subscribes**. Today that's just
notifications-service. Tomorrow it's audit-service, billing-service, a
search indexer, an analytics pipeline. Each new consumer is a new service
with no change to issues.

## The pipeline at a glance

```
                                   mjira.events  (topic exchange)
                                          │
                                          │  routing_key = "issue.created"
                                          ▼
       ┌──────────┐  publish        ┌────────────┐
       │ issues   │────────────────▶│  RabbitMQ  │
       │ service  │                 └─────┬──────┘
       └──────────┘                       │  binding: "issue.*"
                                          ▼
                              notifications.issue.events  (queue)
                                          │
                                          │  basic_consume + manual ack
                                          ▼
                                   ┌──────────────┐
                                   │ this service │  ──SMTP──▶  MailHog
                                   └──────────────┘
```

Concretely:

1. `issues` calls `publish_event("issue.created", {...})` from
   [shared/events/publisher.py](../../shared/events/publisher.py).
2. RabbitMQ routes the message to every queue whose binding pattern
   matches the routing key.
3. Our queue `notifications.issue.events` is bound with pattern `issue.*`,
   so it receives any `issue.<anything>` event.
4. Our consumer thread reads the message, sends an email, and
   acknowledges. On exception it nacks without requeue (drops the
   message rather than retry-storming).

## RabbitMQ vocabulary, the short version

If you've only worked with HTTP, AMQP introduces four terms you'll see
all over this codebase:

| Term | What it is |
|---|---|
| **Exchange** | Where producers publish. They never publish "to a queue" — only to an exchange. Think of it as a router. |
| **Queue** | Where consumers read from. Messages live here, in order, until acknowledged. |
| **Binding** | A rule that says "exchange X should copy messages to queue Y when the routing key matches pattern Z." |
| **Routing key** | A short string the producer attaches to each message (e.g. `issue.created`). The exchange uses it to decide where the message goes. |

A producer and consumer can come up in any order. The exchange and queue
exist independently of who's connected. If no consumer is running when a
message arrives, RabbitMQ holds it in the queue until one shows up.

## Why a *topic* exchange (and not direct/fanout)?

RabbitMQ has four exchange types; we use **topic** because it gives us a
small bit of glob-style routing without committing to specific consumer
shapes:

- **direct** — routing key must match exactly. Fine if every event has
  exactly one queue interested, but inflexible.
- **fanout** — every bound queue gets every message. No filtering at all.
  Wasteful if a consumer only cares about a subset.
- **topic** — routing key is a dotted string; bindings are glob patterns
  with `*` (one segment) and `#` (zero or more segments).
- **headers** — match on message headers instead of routing key. Niche.

With `mjira.events` as a topic exchange we get one bus that scales:

- This service binds `issue.*` and gets all issue events today.
- A future audit-service can bind `#` and get **everything**.
- A future "issue assigned" Slack bot binds `issue.assigned` only.

No change required on the publisher side for any of those new consumers.

## Why durable queue + manual acks?

A queue declared `durable=True` survives broker restarts. A message
published with `delivery_mode=2` (we set this in
[shared/events/publisher.py](../../shared/events/publisher.py)) is
persisted to disk before the broker confirms the publish. Together,
those two flags mean **a message is not lost if RabbitMQ restarts**
between publish and consume.

Manual acks (vs auto-ack on receive) mean the broker keeps the message
"unacknowledged" until our handler explicitly calls `basic_ack`. If our
process dies mid-handler, the broker re-delivers the message to whichever
consumer comes back online. This is **at-least-once delivery**.

The price: handlers must be **idempotent** — re-running them with the
same input must produce the same outcome. Our current "send email" is
not strictly idempotent (the user could get the email twice), which is
acceptable for notifications. For something like "charge a credit card"
you'd add a deduplication key.

On exception we `basic_nack(requeue=False)` rather than letting the
message bounce back into the queue. Why: a message that crashed our
handler will almost certainly crash it again, and we'd lock the consumer
in a retry loop. Production systems usually configure a **dead-letter
exchange** so nacked messages land in an inspection queue. We don't have
one yet — file under "Phase 2.5."

## Why a daemon thread, not async, not a separate process?

Three options for running the consumer alongside FastAPI:

1. **Separate process** (`docker-compose.yml` runs two containers per
   service: web + worker). Cleanest separation; doubles your container
   count.
2. **Daemon thread inside the FastAPI process** (what we do). One
   container, one process. The consumer runs in a thread spawned from
   the lifespan handler; FastAPI keeps serving HTTP on the main thread.
3. **asyncio task inside the FastAPI event loop** (would require
   `aio-pika`). Cleanest single-process option — but the rest of this
   codebase is sync, and switching paradigms in one service hurts more
   than it helps.

For a learning project with one consumer per service, option 2 is the
sweet spot. The thread is `daemon=True` so it dies when the process
dies; nothing to clean up at shutdown. See
[app/consumer.py](app/consumer.py) for the ~70 lines that make this
work.

## Delivery guarantees, honestly

We have **at-least-once on the broker side**: once a message is in the
exchange, RabbitMQ retries until a consumer acks it.

We do **not** yet have at-least-once on the publisher side. The current
[issues route](../issues/app/routes.py) does:

```python
db.commit()
publish_event("issue.created", {...})  # TODO(phase 2.5): outbox
```

If the issues process is killed between those two lines, the issue is
in the database but no event is ever published — silently lost. The
fix is the **transactional outbox pattern**: write the event into a
local `outbox` table inside the same transaction as the issue, then
have a separate worker drain the outbox to RabbitMQ with retries. The
canonical references are Pat Helland's *"Life Beyond Distributed
Transactions: An Apostate's Opinion"* (CIDR 2007) and Chris Richardson's
*Microservices Patterns*, chapter on the outbox pattern.

We're punting that to Phase 2.5 because the educational point of *this*
phase is "wire async events between services," and the outbox is its
own focused topic worth doing as its own exercise.

## Why MailHog?

MailHog is a fake SMTP server that captures everything sent to it and
exposes a web UI + JSON API to inspect the messages. It accepts mail
from anyone, never delivers anywhere, and runs as a single docker
container. Perfect for development and integration tests:

- **SMTP**: `mailhog:1025` inside the docker network, `localhost:1025`
  from the host.
- **Web UI**: http://localhost:8025 — browse received emails.
- **JSON API**: `GET http://localhost:8025/api/v2/messages` — used by
  [tests/test_events.py](../../tests/test_events.py) to assert the
  pipeline worked end-to-end.

In production this service would point at a real SMTP relay (Postmark,
SES, SendGrid, your own postfix) — same code, different `SMTP_HOST` and
auth. The `smtplib` call doesn't change.

## Configuration

All env vars are **required** (the service crashes loudly on startup if
any is missing — see the `os.environ[...]` reads in
[app/email.py](app/email.py) and [app/consumer.py](app/consumer.py)).
This matches the convention in the rest of the project; defaults that
silently work in docker-compose but break elsewhere were judged worse
than a loud `KeyError`.

| Var | Set by | Notes |
|---|---|---|
| `RABBITMQ_URL` | docker-compose, interpolated from `.env` | `amqp://user:pass@rabbitmq:5672/` |
| `SMTP_HOST` | docker-compose (literal `mailhog`) | docker-network DNS name |
| `SMTP_PORT` | docker-compose (literal `1025`) | MailHog's SMTP port |
| `SMTP_FROM` | docker-compose, interpolated from `.env` | the `From:` header on outgoing mail |
| `SERVICE_PORT` | docker-compose | uvicorn bind port |

## Files

| File | What it does |
|---|---|
| [app/main.py](app/main.py) | FastAPI app, declares `/notifications/health`, spawns the consumer thread in `lifespan` |
| [app/consumer.py](app/consumer.py) | The pika consumer: declares the exchange + queue + binding, dispatches messages, handles reconnects |
| [app/email.py](app/email.py) | Tiny `smtplib` wrapper. Same code talks to MailHog or any real SMTP relay |
| [Dockerfile](Dockerfile) | Same shape as the other services; copies `shared/` for the publisher import |
| [entrypoint.sh](entrypoint.sh) | Just runs uvicorn — no alembic step because this service has no database |

## Local debugging

```bash
# Inspect the broker — exchanges, queues, message rates, bindings
open http://localhost:15672      # user / pass from .env

# See what emails the service has sent
open http://localhost:8025

# Watch the consumer's logs live
docker compose logs -f notifications

# Manually republish an event without going through issues
docker compose exec rabbitmq rabbitmqadmin publish \
  exchange=mjira.events routing_key=issue.created \
  payload='{"event":"issue.created","tenant_id":"abc","issue":{"id":"x","title":"manual test"}}'
```
