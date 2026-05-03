"""End-to-end test for the audit pipeline.

Creates, updates, and deletes an issue via the gateway, then peeks
directly at audit_db to confirm all three events landed. We connect to
postgres via the host-exposed port (5432) rather than going through the
gateway because audit-service has no read API yet — the test acts as a
stand-in for ops poking at the table directly.
"""
from __future__ import annotations

import os
import time

import psycopg

PG_DSN = os.getenv(
    "AUDIT_DB_DSN",
    "host=localhost port=5432 dbname=audit_db "
    f"user={os.environ['POSTGRES_USER']} password={os.environ['POSTGRES_PASSWORD']}",
)


def _wait_for_event(tenant_id: str, event_type: str, deadline_s: float = 10.0) -> dict | None:
    deadline = time.time() + deadline_s
    while time.time() < deadline:
        try:
            with psycopg.connect(PG_DSN) as conn, conn.cursor() as cur:
                cur.execute(
                    "SELECT payload FROM audit_events "
                    "WHERE tenant_id = %s AND event_type = %s "
                    "ORDER BY occurred_at DESC LIMIT 1",
                    (tenant_id, event_type),
                )
                row = cur.fetchone()
                if row is not None:
                    return row[0]
        except psycopg.OperationalError:
            pass
        time.sleep(0.3)
    return None


def test_issue_lifecycle_lands_in_audit_log(client, tenant_user, auth_header):
    pr = client.post(
        "/projects",
        headers=auth_header(tenant_user.token),
        json={"key": "AUD", "name": "Audit"},
    )
    assert pr.status_code == 201, pr.text
    project_id = pr.json()["id"]

    ic = client.post(
        "/issues",
        headers=auth_header(tenant_user.token),
        json={"project_id": project_id, "title": "audit me"},
    )
    assert ic.status_code == 201, ic.text
    issue_id = ic.json()["id"]

    iu = client.patch(
        f"/issues/{issue_id}",
        headers=auth_header(tenant_user.token),
        json={"status": "in_progress"},
    )
    assert iu.status_code == 200, iu.text

    idel = client.delete(f"/issues/{issue_id}", headers=auth_header(tenant_user.token))
    assert idel.status_code == 204, idel.text

    created = _wait_for_event(tenant_user.tenant_id, "issue.created")
    updated = _wait_for_event(tenant_user.tenant_id, "issue.updated")
    deleted = _wait_for_event(tenant_user.tenant_id, "issue.deleted")

    assert created is not None, "issue.created never reached audit log"
    assert created["issue"]["id"] == issue_id

    assert updated is not None, "issue.updated never reached audit log"
    assert "status" in updated.get("changed_fields", [])

    assert deleted is not None, "issue.deleted never reached audit log"
    assert deleted["issue"]["id"] == issue_id


def test_audit_dedupes_on_event_id(client, tenant_user, auth_header):
    """Same event_id arriving twice should produce one row, not two.

    We assert the constraint exists rather than trying to force a
    duplicate from the publisher (which generates a fresh event_id per
    call). The unique index is the actual safety net under at-least-once."""
    with psycopg.connect(PG_DSN) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM pg_constraint WHERE conname = 'uq_audit_events_event_id'"
        )
        row = cur.fetchone()
        assert row is not None and row[0] == 1, (
            "uq_audit_events_event_id missing — at-least-once retries would duplicate rows"
        )
