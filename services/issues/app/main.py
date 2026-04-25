from contextlib import asynccontextmanager

from fastapi import FastAPI

from .db import Base, engine
from .models import Issue  # noqa: F401
from .routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="issues-service",
    docs_url="/issues/docs",
    redoc_url="/issues/redoc",
    openapi_url="/issues/openapi.json",
    lifespan=lifespan,
)


@app.get("/issues/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "issues"}


app.include_router(router)
