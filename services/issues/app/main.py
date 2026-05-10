from fastapi import FastAPI

from shared.cache import RateLimitMiddleware
from shared.observability import instrument_fastapi_app, setup_tracing

from .routes import router

setup_tracing("issues-service")

app = FastAPI(
    title="issues-service",
    docs_url="/issues/docs",
    redoc_url="/issues/redoc",
    openapi_url="/issues/openapi.json",
)
instrument_fastapi_app(app)
app.add_middleware(RateLimitMiddleware)


@app.get("/issues/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "issues"}


app.include_router(router)
