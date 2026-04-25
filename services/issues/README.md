# issues-service

Owns issues (tickets). Every issue belongs to a project, which belongs to a tenant.

## Responsibilities

- Create / list / get / patch / delete issues within the caller's active tenant
- Filter listings by `project_id` and `status`
- Enforce the **tenant isolation invariant** (404, never 403, for cross-tenant access)

## Endpoints

| Method | Path | Auth | Body / Query | Returns |
|---|---|---|---|---|
| POST | `/issues` | bearer + tenant | `{project_id, title, description?, assignee_id?}` | `201` issue |
| GET | `/issues?project_id=&status=` | bearer + tenant | optional filters | issues in caller's tenant |
| GET | `/issues/{id}` | bearer + tenant | — | issue or 404 |
| PATCH | `/issues/{id}` | bearer + tenant | partial: `title`, `description`, `status`, `assignee_id` | updated issue |
| DELETE | `/issues/{id}` | bearer + tenant | — | `204` or 404 |
| GET | `/issues/health` | — | — | — |
| GET | `/issues/docs` · `/issues/redoc` · `/issues/openapi.json` | — | — | Interactive API docs |

`status` ∈ `{open, in_progress, done}`, default `open`.

## Tenant context

Same rule as projects-service: the `require_tenant` dependency in [app/deps.py](app/deps.py) requires a `tenant_id` claim, and every query filters by it. `tenant_id` is never accepted from the request payload.

> **Not yet validated:** the service does not (yet) verify that `project_id` exists in projects-service or belongs to the same tenant. In a real system you'd either validate via an HTTP call or consume a `project.created` event. This is acceptable for Phase 1 because the cross-tenant `tenant_id` filter still prevents leakage between tenants — the worst case is an issue pointing at a non-existent project_id within your own tenant.

## Schema (`issues_db`)

```sql
issues (
  id           UUID PRIMARY KEY,
  tenant_id    UUID NOT NULL,
  project_id   UUID NOT NULL,
  title        TEXT NOT NULL,
  description  TEXT,
  status       TEXT CHECK (status IN ('open','in_progress','done')) DEFAULT 'open',
  assignee_id  UUID,
  created_by   UUID NOT NULL,
  created_at   TIMESTAMPTZ DEFAULT now()
)
INDEX ON issues (tenant_id, project_id);
```

`project_id` is **not** a FK to projects-service. Cross-DB joins are forbidden.

## Env vars

| Var | Purpose |
|---|---|
| `DATABASE_URL` | `postgresql+psycopg://user:pass@db:5432/issues_db` |
| `JWT_SECRET` | shared HS256 secret |
| `JWT_ALGORITHM` | default `HS256` |

## Layout

```
app/
  main.py     FastAPI app
  routes.py   /issues CRUD
  models.py   Issue
  schemas.py  Pydantic in/out
  deps.py     require_tenant
  db.py       engine + session
```
