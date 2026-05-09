from fastapi import FastAPI

from shared.cache import RateLimitMiddleware

from .routes import router

app = FastAPI(
    title="issues-service",
    docs_url="/issues/docs",
    redoc_url="/issues/redoc",
    openapi_url="/issues/openapi.json",
)
app.add_middleware(RateLimitMiddleware)


@app.get("/issues/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "issues"}


app.include_router(router)
