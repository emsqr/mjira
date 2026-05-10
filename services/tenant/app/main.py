from fastapi import FastAPI

from shared.cache import RateLimitMiddleware
from shared.observability import instrument_fastapi_app, setup_tracing

from .routes import internal_router, router

setup_tracing("tenant-service")

app = FastAPI(
    title="tenant-service",
    docs_url="/tenants/docs",
    redoc_url="/tenants/redoc",
    openapi_url="/tenants/openapi.json",
)
instrument_fastapi_app(app)
app.add_middleware(RateLimitMiddleware)


@app.get("/tenants/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "tenant"}


app.include_router(router)
app.include_router(internal_router)
