from fastapi import FastAPI

from shared.cache import RateLimitMiddleware
from shared.observability import instrument_fastapi_app, setup_tracing

from .routes import router

setup_tracing("projects-service")

app = FastAPI(
    title="projects-service",
    docs_url="/projects/docs",
    redoc_url="/projects/redoc",
    openapi_url="/projects/openapi.json",
)
instrument_fastapi_app(app)
app.add_middleware(RateLimitMiddleware)


@app.get("/projects/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "projects"}


app.include_router(router)
