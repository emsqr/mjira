from fastapi import FastAPI

from .routes import router

app = FastAPI(
    title="auth-service",
    docs_url="/auth/docs",
    redoc_url="/auth/redoc",
    openapi_url="/auth/openapi.json",
)


@app.get("/auth/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "auth"}


app.include_router(router)
