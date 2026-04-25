from contextlib import asynccontextmanager

from fastapi import FastAPI

from .db import Base, engine
from .models import User  # noqa: F401  (registers model with Base)
from .routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="auth-service",
    docs_url="/auth/docs",
    redoc_url="/auth/redoc",
    openapi_url="/auth/openapi.json",
    lifespan=lifespan,
)


@app.get("/auth/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "auth"}


app.include_router(router)
