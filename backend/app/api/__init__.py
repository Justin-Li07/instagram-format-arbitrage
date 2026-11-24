"""HTTP API package: `api_router` aggregates every resource router under /api."""
from fastapi import APIRouter

from app.config import API_PREFIX
from app.api.routes import (
    creators,
    formats,
    health,
    hooks,
    ingest,
    niches,
    outliers,
    reels,
    runs,
    velocity,
)

api_router = APIRouter(prefix=API_PREFIX)
for _module in (health, niches, runs, ingest, outliers, formats, velocity, hooks, creators, reels):
    api_router.include_router(_module.router)

__all__ = ["api_router"]
