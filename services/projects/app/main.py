from fastapi import FastAPI

from .routes import router

app = FastAPI(
    title="projects-service",
    docs_url="/projects/docs",
    redoc_url="/projects/redoc",
    openapi_url="/projects/openapi.json",
)


@app.get("/projects/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "projects"}


app.include_router(router)
