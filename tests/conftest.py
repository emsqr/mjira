"""Integration-test fixtures.

These tests hit the running stack via the gateway. Bring it up with `make up`
before running. Each test uses uuid-suffixed emails / tenant slugs so the
tests are isolated from each other and from any data already in the DB.
"""
from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from dataclasses import dataclass

import httpx
import pytest

GATEWAY = os.getenv("MJIRA_GATEWAY", "http://localhost:8080")
DEFAULT_PASSWORD = "TestPassword123!"


@dataclass(frozen=True)
class User:
    """A signed-up user with no tenant context yet."""

    user_id: str
    email: str
    password: str
    token: str  # JWT with no tenant_id


@dataclass(frozen=True)
class TenantUser:
    """A user who owns a tenant. Token is tenant-scoped."""

    user_id: str
    email: str
    password: str
    tenant_id: str
    tenant_slug: str
    token: str  # JWT with tenant_id + role=owner


def _rand(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def _bearer(token: str) -> dict[str, str]:
    return {"authorization": f"Bearer {token}"}


@pytest.fixture(scope="session")
def gateway_url() -> str:
    return GATEWAY


@pytest.fixture(scope="session", autouse=True)
def _stack_must_be_up(gateway_url: str) -> None:
    """Fail loudly if the gateway isn't reachable — no silent skips."""
    try:
        r = httpx.get(f"{gateway_url}/health", timeout=2.0)
        r.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        pytest.exit(
            f"Gateway not reachable at {gateway_url}. Run `make up` first.\n"
            f"Underlying error: {exc}",
            returncode=2,
        )


@pytest.fixture()
def client(gateway_url: str) -> Iterator[httpx.Client]:
    with httpx.Client(base_url=gateway_url, timeout=10.0) as c:
        yield c


# -------- Helpers usable as plain functions inside tests --------

def signup(client: httpx.Client, email: str | None = None) -> User:
    email = email or f"{_rand('user')}@example.com"
    r = client.post(
        "/auth/signup",
        json={"email": email, "password": DEFAULT_PASSWORD},
    )
    r.raise_for_status()
    user_id = r.json()["id"]

    tok = client.post(
        "/auth/login",
        json={"email": email, "password": DEFAULT_PASSWORD},
    ).json()["access_token"]
    return User(user_id=user_id, email=email, password=DEFAULT_PASSWORD, token=tok)


def make_tenant_user(client: httpx.Client, tenant_name: str | None = None) -> TenantUser:
    """Sign up a user, create a tenant, and re-login with tenant_slug."""
    user = signup(client)
    slug = _rand("t")
    name = tenant_name or f"Tenant {slug}"
    r = client.post(
        "/tenants",
        headers=_bearer(user.token),
        json={"name": name, "slug": slug},
    )
    r.raise_for_status()
    tenant_id = r.json()["id"]

    tok = client.post(
        "/auth/login",
        json={
            "email": user.email,
            "password": user.password,
            "tenant_slug": slug,
        },
    ).json()["access_token"]
    return TenantUser(
        user_id=user.user_id,
        email=user.email,
        password=user.password,
        tenant_id=tenant_id,
        tenant_slug=slug,
        token=tok,
    )


# -------- Fixture wrappers --------

@pytest.fixture()
def fresh_user(client: httpx.Client) -> User:
    return signup(client)


@pytest.fixture()
def tenant_user(client: httpx.Client) -> TenantUser:
    return make_tenant_user(client)


@pytest.fixture()
def two_tenants(client: httpx.Client) -> tuple[TenantUser, TenantUser]:
    """Two unrelated tenant users — for cross-tenant isolation tests."""
    return make_tenant_user(client), make_tenant_user(client)


@pytest.fixture()
def auth_header():
    """Build a bearer-auth header dict from a token."""
    return _bearer
