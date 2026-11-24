"""Outlier reels: views far above the creator's own median, or big views from small creators."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.analytics._common import is_outlier, is_small, load_reels, reel_url


def find_outliers(
    session: Session,
    niche: str | None = None,
    min_multiple: float = 10.0,
    small_creator_max_followers: int = 10_000,
    small_creator_min_views: int = 100_000,
    limit: int | None = 200,
) -> list[dict]:
    """Reels whose latest views >= min_multiple x creator median (median over latest views),
    plus small-creator reels (followers <= max) with >= small_creator_min_views even below the multiple.
    Sorted by multiple desc, then views desc."""
    out = []
    for r in load_reels(session, niche):
        multiple = r.multiple or 0.0
        if not is_outlier(r.views, multiple, r.followers, min_multiple,
                          small_creator_max_followers, small_creator_min_views):
            continue
        out.append({
            "code": r.code,
            "url": reel_url(r.code),
            "creator": r.creator,
            "niche": r.niche,
            "followers": r.followers,
            "views": r.views,
            "creator_median": r.creator_median,
            "multiple": round(multiple, 3),
            "is_small_creator": is_small(r.followers, small_creator_max_followers),
            "format": r.format,
            "hook": r.hook,
        })
    out.sort(key=lambda d: (d["multiple"], d["views"]), reverse=True)
    return out[:limit] if limit is not None else out
