from contextlib import asynccontextmanager

from fastapi import FastAPI

from shared.observability import instrument_fastapi_app, setup_tracing

from .consumer import start_in_background

setup_tracing("notifications-service")


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
instrument_fastapi_app(app)


@app.get("/notifications/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "notifications"}
