# audit-service

Write-only consumer that persists every domain event to a durable audit
log. Binds `#` (catch-all) to the `mjira.events` topic exchange — so any
event any service publishes, present or future, lands here without code
changes to either side.

## What lives here

```
audit_events
  id            uuid PK
  event_id      uuid UNIQUE        -- dedup key from the publisher
  occurred_at   timestamptz        -- when the event happened (publisher clock)
  event_type    text               -- the routing key, e.g. "issue.created"
  tenant_id     uuid NULL          -- null for events with no tenant context
  payload       jsonb              -- the full event body
  ix (tenant_id, event_type)       -- for the future query API
```

## Idempotency

The bus is at-least-once. If a consumer crashes mid-handler, RabbitMQ
will re-deliver the same message to the next consumer (or to the same
one after restart). To avoid duplicate audit rows we use the
`event_id` injected by [shared/events/publisher.py](../../shared/events/publisher.py)
and a `UNIQUE` constraint:

```python
INSERT INTO audit_events (...) VALUES (...)
ON CONFLICT (event_id) DO NOTHING
```

That makes re-delivery a no-op at the storage layer rather than relying
on the consumer never crashing.

## Why no query API yet?

A read API needs all the same machinery the other services have:
auth-aware tenant filtering, the 404-not-403 invariant for cross-tenant
reads, pagination, possibly a dedicated index pattern. That's its own
focused exercise. V1 is "events get persisted." V2 is "ops can read
them." Marker is in [app/main.py](app/main.py).

For ad-hoc inspection in dev:

```bash
docker compose exec db psql -U postgres -d audit_db \
  -c "SELECT event_type, tenant_id, occurred_at FROM audit_events ORDER BY occurred_at DESC LIMIT 20;"
```

## See also

- [services/notifications/README.md](../notifications/README.md) — covers
  the broader concepts (topic exchanges, durable queues, daemon-thread
  consumers, at-least-once delivery). audit-service uses the same
  patterns; that doc is the single source of truth for the messaging
  side of the project.
- [shared/events/publisher.py](../../shared/events/publisher.py) — where
  `event_id` and `occurred_at` get injected.
