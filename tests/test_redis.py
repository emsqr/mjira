"""Redis-backed features: JWT blocklist (logout) and per-tenant rate limit.

Rate-limit test pre-loads the bucket via direct Redis SET so it doesn't
depend on the configured limit being small enough to exhaust by hammering.
"""
from __future__ import annotations

import os
import time

import pytest
import redis as redis_lib


@pytest.fixture(scope="module")
def redis_client() -> redis_lib.Redis:
    return redis_lib.Redis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        decode_responses=True,
    )


# -------- Blocklist (logout) --------


def test_logout_revokes_token(client, fresh_user, auth_header):
    assert client.get("/auth/me", headers=auth_header(fresh_user.token)).status_code == 200

    r = client.post("/auth/logout", headers=auth_header(fresh_user.token))
    assert r.status_code == 204

    r = client.get("/auth/me", headers=auth_header(fresh_user.token))
    assert r.status_code == 401
    assert "revoked" in r.json()["detail"].lower()


def test_logout_only_affects_the_logged_out_token(client, fresh_user, auth_header):
    other = client.post(
        "/auth/login",
        json={"email": fresh_user.email, "password": fresh_user.password},
    ).json()["access_token"]

    client.post("/auth/logout", headers=auth_header(fresh_user.token)).raise_for_status()

    assert client.get("/auth/me", headers=auth_header(fresh_user.token)).status_code == 401
    assert client.get("/auth/me", headers=auth_header(other)).status_code == 200


def test_logout_requires_auth(client):
    assert client.post("/auth/logout").status_code == 401


def test_revoked_token_rejected_across_services(client, tenant_user, auth_header):
    assert client.get("/projects", headers=auth_header(tenant_user.token)).status_code == 200

    client.post("/auth/logout", headers=auth_header(tenant_user.token)).raise_for_status()

    assert client.get("/projects", headers=auth_header(tenant_user.token)).status_code == 401
    assert client.get("/issues", headers=auth_header(tenant_user.token)).status_code == 401


# -------- Rate limit --------


def test_rate_limit_returns_429_when_bucket_exhausted(
    client, tenant_user, auth_header, redis_client
):
    """Pre-load the per-tenant bucket to the configured limit, then verify
    the next request gets 429 with Retry-After. This avoids depending on the
    limit being small enough to hammer through in real time."""
    limit = int(os.getenv("RATE_LIMIT_PER_MINUTE", "600"))
    bucket = int(time.time() // 60)
    key = f"ratelimit:tenant:{tenant_user.tenant_id}:{bucket}"
    redis_client.set(key, str(limit), ex=70)

    r = client.get("/projects", headers=auth_header(tenant_user.token))
    assert r.status_code == 429
    assert r.headers.get("Retry-After") == "60"
    assert "rate limit" in r.json()["detail"].lower()


def test_rate_limit_does_not_block_health(client, redis_client):
    """Health probes are exempt — pre-load the IP bucket and confirm
    /health still returns 200."""
    limit = int(os.getenv("RATE_LIMIT_PER_MINUTE", "600"))
    bucket = int(time.time() // 60)
    # match whatever the middleware will key on for unauth requests
    key = f"ratelimit:ip:127.0.0.1:{bucket}"
    redis_client.set(key, str(limit + 100), ex=70)

    assert client.get("/auth/health").status_code == 200
