from contextlib import asynccontextmanager

from fastapi import FastAPI

from .db import Base, engine
from .models import Project  # noqa: F401
from .routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="projects-service",
    docs_url="/projects/docs",
    redoc_url="/projects/redoc",
    openapi_url="/projects/openapi.json",
    lifespan=lifespan,
)


@app.get("/projects/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "projects"}


app.include_router(router)
