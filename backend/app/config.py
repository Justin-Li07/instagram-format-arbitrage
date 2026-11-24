"""App-level settings for the API layer (env-overridable)."""
from __future__ import annotations

import os

NICHES: tuple[str, ...] = ("engineering", "university-life", "startups-tech", "growth-viral")

CORS_ORIGINS: list[str] = [
    o.strip()
    for o in os.environ.get(
        "FA_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if o.strip()
]

API_PREFIX = "/api"
APP_TITLE = "Format Arbitrage Tracker API"
APP_VERSION = "0.1.0"
