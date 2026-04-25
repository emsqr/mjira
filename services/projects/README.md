# projects-service

Owns projects. Every project is scoped to a single tenant.

## Responsibilities

- Create / list / get / delete projects within the caller's active tenant
- Enforce the **tenant isolation invariant**: a project from tenant A is invisible (404, never 403) to a user whose JWT carries tenant B

## Endpoints

| Method | Path | Auth | Body | Returns |
|---|---|---|---|---|
| POST | `/projects` | bearer + tenant | `{key, name}` | `201` project |
| GET | `/projects` | bearer + tenant | — | projects in caller's tenant |
| GET | `/projects/{id}` | bearer + tenant | — | project, or 404 |
| DELETE | `/projects/{id}` | bearer + tenant | — | `204`, or 404 |
| GET | `/projects/health` | — | — | — |
| GET | `/projects/docs` · `/projects/redoc` · `/projects/openapi.json` | — | — | Interactive API docs |

`key` is upper-cased and must match `^[A-Z][A-Z0-9]{1,9}$` (e.g. `ENG`, `MKT`). Unique per tenant.

## Tenant context

The `require_tenant` dependency in [app/deps.py](app/deps.py) rejects any token without a `tenant_id` claim. `tenant_id` is **always** taken from the JWT — never from request body or query string. Every read filters `WHERE tenant_id = current.tenant_id`; every write sets `tenant_id = current.tenant_id`.

## Schema (`projects_db`)

```sql
projects (
  id          UUID PRIMARY KEY,
  tenant_id   UUID NOT NULL,             -- hot filter, indexed
  key         TEXT NOT NULL,
  name        TEXT NOT NULL,
  created_by  UUID NOT NULL,
  created_at  TIMESTAMPTZ DEFAULT now(),
  UNIQUE (tenant_id, key)
)
INDEX ON projects (tenant_id);
```

`tenant_id` and `created_by` are not FKs — they point at `tenant_db.tenants.id` and `auth_db.users.id` respectively.

## Env vars

| Var | Purpose |
|---|---|
| `DATABASE_URL` | `postgresql+psycopg://user:pass@db:5432/projects_db` |
| `JWT_SECRET` | shared HS256 secret |
| `JWT_ALGORITHM` | default `HS256` |

## Layout

```
app/
  main.py     FastAPI app
  routes.py   /projects CRUD
  models.py   Project
  schemas.py  Pydantic in/out
  deps.py     require_tenant — rejects tokens without tenant_id
  db.py       engine + session
```
