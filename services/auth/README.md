# auth-service

Owns user identity. Stores users, verifies passwords, and mints JWTs.

## Responsibilities

- Sign up new users (`POST /signup`)
- Verify credentials and issue JWTs (`POST /login`)
- Return the current user (`GET /me`)
- During login with a `tenant_slug`, call **tenant-service** at `GET /internal/memberships/lookup` to embed the active `tenant_id` + `role` claims in the token

## Endpoints

All paths are prefixed with `/auth` — the FastAPI router carries the prefix and the nginx gateway forwards `/auth/*` through unchanged (no prefix-stripping).

| Method | Path | Auth | Body / Query | Returns |
|---|---|---|---|---|
| POST | `/auth/signup` | — | `{email, password}` | `201` user |
| POST | `/auth/login` | — | `{email, password, tenant_slug?}` | `{access_token, tenant_id?, role?}` |
| GET | `/auth/me` | bearer | — | current user |
| GET | `/auth/health` | — | — | `{status:"ok"}` |
| GET | `/auth/docs` · `/auth/redoc` · `/auth/openapi.json` | — | — | Interactive API docs |

A login **without** `tenant_slug` mints a token that has only `sub` (user_id). Tenant-scoped services (`projects`, `issues`) reject such tokens with `403 — Token has no tenant context`. Re-login with a slug to switch tenants.

## Schema (`auth_db`)

```sql
users (
  id            UUID PRIMARY KEY,
  email         TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  created_at    TIMESTAMPTZ DEFAULT now()
)
```

Tables are created at startup via `Base.metadata.create_all()` — no Alembic yet.

## Env vars

| Var | Purpose |
|---|---|
| `DATABASE_URL` | `postgresql+psycopg://user:pass@db:5432/auth_db` |
| `JWT_SECRET` | shared HS256 secret — must match every other service |
| `JWT_ALGORITHM` | default `HS256` |
| `JWT_EXPIRE_MINUTES` | default `60` |
| `TENANT_SERVICE_URL` | base URL for the tenant service (default `http://tenant:8000`) |

## Layout

```
app/
  main.py       FastAPI app, table create on startup
  routes.py     /signup /login /me
  models.py     User
  schemas.py    SignupRequest, LoginRequest, TokenResponse, UserOut
  security.py   bcrypt password hash/verify
  db.py         SQLAlchemy engine + session
```

## Notes

- Passwords are hashed with bcrypt via passlib. `bcrypt` is pinned to `4.2.0` because passlib 1.7.4's backend self-test crashes on bcrypt 5.x.
- Email is lower-cased on signup and login.
- Auth-service is the **only service that calls another service synchronously** (auth → tenant during login). All other inter-service relationships are by ID with no FK across DBs.
