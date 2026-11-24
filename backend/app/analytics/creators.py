"""Per-creator summaries."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics._common import (
    follower_bucket,
    is_small,
    iso,
    latest_followers,
    load_reels,
    median,
    reel_url,
    row_is_outlier,
    to_naive_utc,
)
from app.db.models import Creator, CreatorSnapshot


def creator_summary(session: Session, username: str) -> dict | None:
    """Follower history, reel count, median views, all reels and outlier reels. None if unknown."""
    creator = session.execute(select(Creator).where(Creator.username == username)).scalar_one_or_none()
    if creator is None:
        return None
    snaps = session.execute(
        select(CreatorSnapshot).where(CreatorSnapshot.creator_id == creator.id)
    ).scalars().all()
    history = sorted(
        ((to_naive_utc(s.scraped_at), s.id, s.followers) for s in snaps), key=lambda t: (t[0], t[1])
    )
    rows = load_reels(session, creator_id=creator.id)
    followers = latest_followers(session, [creator.id]).get(creator.id)
    reels = []
    for r in sorted(rows, key=lambda r: r.views, reverse=True):
        reels.append({
            "code": r.code,
            "url": reel_url(r.code),
            "views": r.views,
            "multiple": round(r.multiple or 0.0, 3),
            "is_outlier": row_is_outlier(r),
            "format": r.format,
            "hook": r.hook,
            "first_seen_at": iso(r.first_seen_at),
            "posted_at": iso(r.posted_at),
            "snapshots": len(r.snapshots),
        })
    return {
        "username": creator.username,
        "niche": creator.niche,
        "first_seen_at": iso(creator.first_seen_at),
        "last_seen_at": iso(creator.last_seen_at),
        "followers": followers,
        "bucket": follower_bucket(followers),
        "is_small_creator": is_small(followers),
        "follower_history": [{"scraped_at": iso(ts), "followers": f} for ts, _id, f in history],
        "reel_count": len(rows),
        "median_views": median(r.views for r in rows),
        "reels": reels,
        "outlier_reels": [r for r in reels if r["is_outlier"]],
    }


def list_creators(session: Session, niche: str | None = None) -> list[dict]:
    """One row per creator, sorted by outlier_count desc then max_views desc."""
    q = select(Creator)
    if niche:
        q = q.where(Creator.niche == niche)
    creators = session.execute(q).scalars().all()
    rows_by_c: dict[int, list] = {}
    for r in load_reels(session, niche):
        rows_by_c.setdefault(r.creator_id, []).append(r)
    fol = latest_followers(session, [c.id for c in creators]) if creators else {}
    out = []
    for c in creators:
        rows = rows_by_c.get(c.id, [])
        followers = fol.get(c.id)
        out.append({
            "username": c.username,
            "niche": c.niche,
            "followers": followers,
            "bucket": follower_bucket(followers),
            "is_small_creator": is_small(followers),
            "reel_count": len(rows),
            "median_views": median(r.views for r in rows),
            "max_views": max((r.views for r in rows), default=None),
            "outlier_count": sum(1 for r in rows if row_is_outlier(r)),
            "first_seen_at": iso(c.first_seen_at),
            "last_seen_at": iso(c.last_seen_at),
        })
    out.sort(key=lambda d: (d["outlier_count"], d["max_views"] or 0), reverse=True)
    return out
