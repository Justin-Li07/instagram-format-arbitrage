"""Hooks used by outlier reels."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.analytics.outliers import find_outliers


def top_hooks(session: Session, niche: str | None = None, limit: int = 50) -> list[dict]:
    """Hooks of outlier reels (labeled with hook text), sorted by multiple then views."""
    out = []
    for o in find_outliers(session, niche=niche, limit=None):
        if not o["hook"]:
            continue
        out.append({
            "code": o["code"],
            "url": o["url"],
            "hook": o["hook"],
            "format": o["format"],
            "views": o["views"],
            "multiple": o["multiple"],
            "creator": o["creator"],
            "followers": o["followers"],
            "is_small_creator": o["is_small_creator"],
            "niche": o["niche"],
        })
    return out[:limit] if limit is not None else out
