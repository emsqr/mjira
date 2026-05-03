from contextlib import asynccontextmanager

from fastapi import FastAPI

from .consumer import start_in_background


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_in_background()
    yield


app = FastAPI(
    title="notifications-service",
    docs_url="/notifications/docs",
    redoc_url="/notifications/redoc",
    openapi_url="/notifications/openapi.json",
    lifespan=lifespan,
)


@app.get("/notifications/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "notifications"}
