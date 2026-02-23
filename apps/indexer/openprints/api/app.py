"""FastAPI application: docs at /docs, OpenAPI at /openapi.json, redoc off."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from openprints.api.deps import close_store, open_store
from openprints.api.routes import designs, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Open store on startup, close on shutdown."""
    await open_store(app)
    try:
        yield
    finally:
        await close_store(app)


app = FastAPI(
    title="OpenPrints API",
    description="List and fetch design metadata from the indexer store.",
    redoc_url=None,
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(designs.router)
