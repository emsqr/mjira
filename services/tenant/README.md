# tenant-service

Owns organizations (tenants) and which users belong to them with which role.

## Responsibilities

- Create tenants (caller becomes `owner`)
- List tenants the current user is a member of
- Manage memberships (add/list members)
- Expose an **internal** lookup used by auth-service during login

## Endpoints

### Public (proxied via gateway)

| Method | Path | Auth | Body / Notes |
|---|---|---|---|
| POST | `/tenants` | bearer | `{name, slug}` — caller becomes `owner` |
| GET | `/tenants` | bearer | tenants the user belongs to |
| GET | `/tenants/{id}` | bearer | member-only |
| POST | `/tenants/{id}/members` | bearer (owner/admin) | `{user_id, role}` |
| GET | `/tenants/{id}/members` | bearer | member-only |
| GET | `/tenants/health` | — | — |
| GET | `/tenants/docs` · `/tenants/redoc` · `/tenants/openapi.json` | — | Interactive API docs |

### Internal (NOT exposed by gateway)

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/internal/memberships/lookup?user_id=&tenant_slug=` | — | Used by auth-service to resolve `tenant_id` + `role` at login time |

The Nginx gateway returns `404` for any `/internal/*` path. These routes are only reachable inside the Compose network.

> **TODO (production):** add a service-to-service auth token on `/internal/*`. Today only network isolation protects them.

## Roles

`owner` ⊃ `admin` ⊃ `member`. Currently:

- `owner` / `admin` — can add members
- `member` — read-only on tenant + memberships

## Schema (`tenant_db`)

```sql
tenants (
  id, name, slug UNIQUE, created_at
)

memberships (
  id, tenant_id → tenants(id), user_id, role,
  UNIQUE (tenant_id, user_id),
  CHECK role IN ('owner','admin','member')
)
```

`user_id` is **not** a FK — it points at `auth_db.users.id`, but cross-service FKs are forbidden in this architecture.

## Env vars

| Var | Purpose |
|---|---|
| `DATABASE_URL` | `postgresql+psycopg://user:pass@db:5432/tenant_db` |
| `JWT_SECRET` | shared HS256 secret |
| `JWT_ALGORITHM` | default `HS256` |

## Layout

```
app/
  main.py       FastAPI app, mounts public + internal routers
  routes.py     /tenants, /tenants/{id}/members, /internal/...
  models.py     Tenant, Membership
  schemas.py    Pydantic in/out
  db.py         engine + session
```
