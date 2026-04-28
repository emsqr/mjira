from fastapi import FastAPI

from .routes import router

app = FastAPI(
    title="issues-service",
    docs_url="/issues/docs",
    redoc_url="/issues/redoc",
    openapi_url="/issues/openapi.json",
)


@app.get("/issues/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "issues"}


app.include_router(router)
