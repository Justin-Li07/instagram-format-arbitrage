"""Outlier reels: views far above the creator's own median, or big views from small creators."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.analytics._common import is_outlier, is_small, load_reels, reel_url

# Breakout definition: a small creator (audience too small to explain the reach) with a huge reel.
BREAKOUT_MAX_FOLLOWERS = 10_000
BREAKOUT_MIN_VIEWS = 500_000
SWEET_SPOT_FOLLOWERS = (1_000, 5_000)


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


def find_breakouts(
    session: Session,
    niche: str | None = None,
    max_followers: int = BREAKOUT_MAX_FOLLOWERS,
    min_views: int = BREAKOUT_MIN_VIEWS,
    limit: int | None = 200,
) -> list[dict]:
    """Proof the content, not the audience, did the work: reels with >= min_views from creators with
    < max_followers followers. Paid partnerships are already excluded by load_reels.

    views_tier: "1M+" or "500K+". follower_tier: "1-5K" (the best case), "<1K" or "5-10K".
    Sorted best first: 1M+ before 500K+, sweet-spot accounts first, then views per follower."""
    out = []
    lo, hi = SWEET_SPOT_FOLLOWERS
    for r in load_reels(session, niche):
        if r.followers is None or r.followers >= max_followers or r.views < min_views:
            continue
        sweet = lo <= r.followers <= hi
        out.append({
            "code": r.code,
            "url": reel_url(r.code),
            "creator": r.creator,
            "niche": r.niche,
            "followers": r.followers,
            "views": r.views,
            "creator_median": r.creator_median,
            "multiple": round(r.multiple or 0.0, 3),
            "is_small_creator": True,
            "views_per_follower": round(r.views / max(r.followers, 1), 2),
            "views_tier": "1M+" if r.views >= 1_000_000 else "500K+",
            "follower_tier": "1-5K" if sweet else ("<1K" if r.followers < lo else "5-10K"),
            "sweet_spot": sweet,
            "format": r.format,
            "hook": r.hook,
        })
    out.sort(key=lambda d: (d["views"] >= 1_000_000, d["sweet_spot"], d["views_per_follower"]), reverse=True)
    return out[:limit] if limit is not None else out
