from contextlib import asynccontextmanager

from fastapi import FastAPI

from .consumer import start_in_background


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_in_background()
    yield


app = FastAPI(
    title="audit-service",
    docs_url="/audit/docs",
    redoc_url="/audit/redoc",
    openapi_url="/audit/openapi.json",
    lifespan=lifespan,
)


@app.get("/audit/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "audit"}


# TODO(later): expose `GET /audit?tenant_id=...&event_type=...` query API.
# Needs to enforce the same multi-tenant 404 invariant the other services do —
# log isolation is a security property, not just a UX nicety.
