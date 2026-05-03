"""End-to-end test for the events pipeline.

Creates an issue via the gateway, then polls MailHog's HTTP API for an email
that contains the new issue's id. This exercises the full chain:
    issues svc --publish--> rabbitmq --bind--> notifications svc --smtp--> mailhog
"""
from __future__ import annotations

import os
import time

import httpx
import pytest

MAILHOG_URL = os.getenv("MAILHOG_URL", "http://localhost:8025")


def _find_email_for_issue(issue_id: str, deadline_s: float = 15.0) -> dict | None:
    deadline = time.time() + deadline_s
    while time.time() < deadline:
        try:
            r = httpx.get(f"{MAILHOG_URL}/api/v2/messages", timeout=2.0)
            r.raise_for_status()
            for msg in r.json().get("items", []):
                body = msg.get("Content", {}).get("Body", "")
                if issue_id in body:
                    return msg
        except httpx.HTTPError:
            pass
        time.sleep(0.5)
    return None


def test_issue_created_emits_email(client, tenant_user, auth_header):
    pr = client.post(
        "/projects",
        headers=auth_header(tenant_user.token),
        json={"key": "EVT", "name": "Events"},
    )
    assert pr.status_code == 201, pr.text
    project_id = pr.json()["id"]

    ir = client.post(
        "/issues",
        headers=auth_header(tenant_user.token),
        json={"project_id": project_id, "title": "fire an event"},
    )
    assert ir.status_code == 201, ir.text
    issue_id = ir.json()["id"]

    msg = _find_email_for_issue(issue_id)
    if msg is None:
        pytest.fail(
            f"no MailHog message contained issue {issue_id} within 15s — "
            "check `docker compose logs notifications rabbitmq mailhog`"
        )

    to_addrs = [a.get("Mailbox", "") + "@" + a.get("Domain", "") for a in msg.get("To", [])]
    assert any(tenant_user.tenant_id in a for a in to_addrs), (
        f"email recipient should encode tenant {tenant_user.tenant_id}, got {to_addrs}"
    )
