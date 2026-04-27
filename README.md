# mjira

Multi-tenant SaaS Jira clone built as 4 FastAPI microservices behind an Nginx gateway, sharing one Postgres instance (one DB per service).

## Run

```bash
cp .env.example .env        # then edit JWT_SECRET
docker compose up --build -d
docker compose ps
```

## Local dev environment (optional)

The services run in Docker — you don't need anything installed on your host to use the app. The local venv exists only so your IDE has something to introspect (autocomplete, go-to-def) and so you can run `pytest` / `ruff` / `mypy` without docker exec.

```bash
uv sync                  # creates .venv/ with the union of all service deps + dev tools
.venv/bin/ruff check .   # lint
.venv/bin/mypy services  # type-check
.venv/bin/pytest         # run integration tests against the running stack
```

The pytest suite in [tests/](tests/) is **integration**, not unit — it talks to the live gateway at `http://localhost:8080`. Bring the stack up first with `make up`, then `make test`. The most important test is [tests/test_isolation.py](tests/test_isolation.py), which verifies the cross-tenant 404 invariant (the spec calls it "the one test that catches almost every tenant-leak bug").

Point your editor at `.venv/bin/python` as the project interpreter. `uv.lock` is committed so everyone gets identical versions; per-service `requirements.txt` files remain the source of truth for the Docker images.

All traffic goes through the gateway on `http://localhost:8080`. Service ports (auth/tenant/projects/issues) are NOT exposed to the host — they're only reachable inside the Compose network.

## API docs

Each service publishes its own Swagger UI / ReDoc / OpenAPI spec, all reached through the gateway:

| Service | Swagger | ReDoc | OpenAPI |
|---|---|---|---|
| auth | http://localhost:8080/auth/docs | /auth/redoc | /auth/openapi.json |
| tenant | http://localhost:8080/tenants/docs | /tenants/redoc | /tenants/openapi.json |
| projects | http://localhost:8080/projects/docs | /projects/redoc | /projects/openapi.json |
| issues | http://localhost:8080/issues/docs | /issues/redoc | /issues/openapi.json |

## Layout

```
gateway/              Nginx reverse proxy
services/auth/        signup, login, /me  →  auth_db
services/tenant/      tenants + memberships  →  tenant_db
services/projects/    projects (tenant-scoped)  →  projects_db
services/issues/      issues (tenant-scoped)  →  issues_db
shared/jwt_utils/     reusable JWT decode + FastAPI dependency
db/init.sql           creates the 4 databases on first boot
```

Each service Dockerfile uses the project root as build context so it can copy `shared/` in alongside its own `app/`.

## End-to-end flow (curl)

```bash
BASE=http://localhost:8080

# 1. Sign up
curl -s -X POST $BASE/auth/signup -H 'content-type: application/json' \
  -d '{"email":"alice@acme.com","password":"alicepw123"}'

# 2. Log in (no tenant yet — token has only user_id)
TOK=$(curl -s -X POST $BASE/auth/login -H 'content-type: application/json' \
  -d '{"email":"alice@acme.com","password":"alicepw123"}' | jq -r .access_token)

# 3. Create tenant — auto-makes the caller "owner"
curl -s -X POST $BASE/tenants -H "authorization: Bearer $TOK" \
  -H 'content-type: application/json' \
  -d '{"name":"Acme Inc","slug":"acme"}'

# 4. Re-log in WITH tenant_slug to get a tenant-scoped token
TOK=$(curl -s -X POST $BASE/auth/login -H 'content-type: application/json' \
  -d '{"email":"alice@acme.com","password":"alicepw123","tenant_slug":"acme"}' | jq -r .access_token)

# 5. Create project + issue
PID=$(curl -s -X POST $BASE/projects -H "authorization: Bearer $TOK" \
  -H 'content-type: application/json' \
  -d '{"key":"ENG","name":"Engineering"}' | jq -r .id)

curl -s -X POST $BASE/issues -H "authorization: Bearer $TOK" \
  -H 'content-type: application/json' \
  -d "{\"project_id\":\"$PID\",\"title\":\"Setup CI\"}"
```

## Tenant isolation invariant

Cross-tenant access returns **404, not 403** — the spec requires that we don't even reveal whether a resource exists in another tenant. Verified end-to-end with two users in two tenants:

- `GET /projects` → other tenant's projects do NOT appear in the list
- `GET /projects/{id}` of another tenant's project → 404
- `GET /issues/{id}` of another tenant's issue → 404

Tenant context comes ONLY from the JWT (`tenant_id` claim). No service ever accepts `tenant_id` from request body or query string.

## Endpoints

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/auth/signup` | — | Create user |
| POST | `/auth/login` | — | Returns JWT; pass `tenant_slug` for tenant-scoped token |
| GET | `/auth/me` | bearer | Current user |
| POST | `/tenants` | bearer | Caller becomes `owner` |
| GET | `/tenants` | bearer | Tenants the user belongs to |
| GET | `/tenants/{id}` | bearer | Member-only |
| POST | `/tenants/{id}/members` | bearer (owner/admin) | Add member |
| GET | `/tenants/{id}/members` | bearer | Member-only |
| POST/GET/DELETE | `/projects[/{id}]` | bearer + tenant | CRUD, tenant-scoped |
| POST/GET/PATCH/DELETE | `/issues[/{id}]` | bearer + tenant | CRUD, tenant-scoped |
| GET | `/{service}/health` | — | Per-service health (e.g. `/auth/health`) |
| GET | `/health` | — | Gateway health |

`/internal/*` routes exist on the tenant service for service-to-service lookups (auth → tenant during login). The gateway returns 404 for any `/internal` path so they're unreachable from outside the Compose network.

## Stop / reset

```bash
docker compose down            # stop, keep DB volume
docker compose down -v         # stop and wipe data
```
