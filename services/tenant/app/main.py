from fastapi import FastAPI

from .routes import internal_router, router

app = FastAPI(
    title="tenant-service",
    docs_url="/tenants/docs",
    redoc_url="/tenants/redoc",
    openapi_url="/tenants/openapi.json",
)


@app.get("/tenants/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "tenant"}


app.include_router(router)
app.include_router(internal_router)
