from contextlib import asynccontextmanager

from fastapi import FastAPI

from .db import Base, engine
from .models import Membership, Tenant  # noqa: F401
from .routes import internal_router, router


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="tenant-service",
    docs_url="/tenants/docs",
    redoc_url="/tenants/redoc",
    openapi_url="/tenants/openapi.json",
    lifespan=lifespan,
)


@app.get("/tenants/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "tenant"}


app.include_router(router)
app.include_router(internal_router)
