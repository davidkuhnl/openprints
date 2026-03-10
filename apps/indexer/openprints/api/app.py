"""FastAPI application: docs at /docs, OpenAPI at /openapi.json, redoc off."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from openprints.api.deps import close_store, open_store
from openprints.api.routes import designs, health, identity


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
app.include_router(health.router)
app.include_router(designs.router)
app.include_router(identity.router)
