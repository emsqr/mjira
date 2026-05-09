from fastapi import FastAPI

from shared.cache import RateLimitMiddleware

from .routes import router

app = FastAPI(
    title="projects-service",
    docs_url="/projects/docs",
    redoc_url="/projects/redoc",
    openapi_url="/projects/openapi.json",
)
app.add_middleware(RateLimitMiddleware)


@app.get("/projects/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "projects"}


app.include_router(router)
