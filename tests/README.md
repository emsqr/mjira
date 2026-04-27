# tests/

Integration tests for mjira. They talk to the live gateway at `http://localhost:8080` over HTTP — no mocking. The whole stack (Nginx + 4 services + Postgres) runs end-to-end.

```bash
make up           # start the stack
make test         # or: .venv/bin/pytest -q
```

The session aborts up-front with a friendly message if the gateway isn't reachable.

## Why integration, not unit

The multi-tenant invariant we care about is *cross-service* and only emerges from real database queries hitting real `tenant_id` filters. Mocks would silently pass while production leaks data. The cost is they need `make up` first and they're slower (~25s for 45 tests). For this project — where the whole point is multi-tenant isolation — that tradeoff is correct.

## How the suite is built

### `conftest.py` — the shared machinery

Three things happen here:

**1. Pre-flight check.**
```python
@pytest.fixture(scope="session", autouse=True)
def _stack_must_be_up(...):
    httpx.get(f"{gateway_url}/health", timeout=2.0).raise_for_status()
```
`autouse=True` runs it once at the start of every test session. If the gateway is down, `pytest.exit(...)` aborts the whole run instead of producing 45 confusing connection errors.

**2. State isolation via uuid.**
```python
def _rand(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"
```
Every email, tenant slug, and project key is uuid-suffixed. Tests don't conflict with each other, don't conflict with data already in the DB, and don't need a "wipe DB before each test" step. The DB just accumulates test users, which is fine in dev. (For CI you'd point at a fresh container.)

**3. Layered factory fixtures.** Three layers of "user readiness," each building on the previous:

```
signup()         →  User       (just signed up; token has no tenant_id)
make_tenant_user → TenantUser  (signed up + owns a tenant; token is tenant-scoped)
two_tenants      → (TenantUser, TenantUser)   (two unrelated owners)
```

A test asks for `tenant_user` and gets a fully-bootstrapped owner with a project-ready token — no boilerplate inside the test body.

## Test files

### `test_health.py` — sanity layer

```python
@pytest.mark.parametrize("path", ["/health", "/auth/health", ...])
def test_health_endpoints_return_ok(client, path):
```
One test body, parametrized over 5 paths → 5 distinct test cases. Plus a test that `/internal/*` returns 404 through the gateway (so service-to-service routes stay unreachable from outside).

### `test_auth.py` — happy path *and* error path

Signup, duplicate-email 409, short-password 422, bad-email 422, login with/without `tenant_slug`, wrong password 401, unknown user 401, `/me` requires bearer, `/me` rejects garbage token. The 422s are interesting — they're `email_validator` rejecting `.local` as a reserved TLD (that's why tests use `@example.com`).

### `test_tenants.py` — role-based access

The key test is `test_non_owner_cannot_add_member`:

1. Owner adds another user as `member`
2. That user logs in with `tenant_slug` → gets a token with `role=member`
3. Member tries to add a third user → **403**

That asserts the role hierarchy actually works in the JWT layer.

### `test_projects.py` — schema + tenant scoping

- `test_create_project_lowercases_key_to_upper` — the pydantic validator works (`mkt` → `MKT`)
- `test_create_project_duplicate_key_per_tenant_conflicts` — `UNIQUE (tenant_id, key)` works
- `test_same_key_allowed_in_different_tenants` — uniqueness scope is per-tenant, not global
- `test_projects_endpoints_require_tenant_context` — a token without `tenant_id` (signup-only login) → 403, exactly the `require_tenant` dependency in [../services/projects/app/deps.py](../services/projects/app/deps.py)

### `test_issues.py` — CRUD + filters

Same shape, plus a fan-out test where 2 projects × 3 issues × 2 statuses verifies that `?project_id=` and `?status=` filters return the right subset.

### `test_isolation.py` — **the one that matters**

Nine assertions in `test_tenant_isolation_full`, all wrapped around two unrelated tenants A and B. After A creates a project + issue, B is verified to:

- Not see them in list endpoints
- Get **404 (not 403)** when fetching by id — because 403 would leak existence
- Get **404 (not 403)** on PATCH and DELETE attempts
- Get `[]` when filtering issues by A's `project_id` — the filter must not bypass the tenant filter
- Find that A's data is untouched after all attacks (PATCH didn't take effect)

Plus `test_tenant_id_in_body_is_ignored`: a malicious client sends `{"key":"ATK", "tenant_id": <B's id>}` while authenticated as A. The created project must belong to A, not B. This is the spec's "**never** accept `tenant_id` from the request body" rule, asserted as code.

## Patterns used

- **`@pytest.mark.parametrize`** for table-driven tests (`test_health`).
- **Fixture composition** — `tenant_user` depends on `client`; `two_tenants` calls the same factory twice. Each test gets fresh state without writing setup.
- **`autouse=True`** for cross-cutting concerns (the pre-flight check) — runs without any test asking for it.
- **Sync `httpx`** — no `pytest-asyncio`. Async would matter if we were testing service code in-process, but we're hitting HTTP — sync is simpler and equally fast.
- **404 vs 403 as a *security property***. Most apps think of these as interchangeable. For tenant-scoped resources they aren't — and the suite enforces that explicitly.
