"""View velocity and how performance relates to follower count."""
from __future__ import annotations

from collections import Counter

from sqlalchemy.orm import Session

from app.analytics._common import (
    BUCKETS,
    ReelRow,
    follower_bucket,
    load_reels,
    median,
    row_is_outlier,
)


def _velocity(r: ReelRow) -> tuple[float, float, str] | None:
    """(views_per_hour, hours_observed, method) or None if not computable."""
    snaps = r.snapshots
    if len(snaps) >= 2:
        t2, v2 = snaps[-1]
        # previous snapshot with a strictly earlier timestamp
        for t1, v1 in reversed(snaps[:-1]):
            hours = (t2 - t1).total_seconds() / 3600.0
            if hours > 0:
                return (v2 - v1) / hours, hours, "snapshots"
    if r.posted_at is not None and snaps:
        t, v = snaps[-1]
        hours = (t - r.posted_at).total_seconds() / 3600.0
        if hours > 0:
            return v / hours, hours, "posted_at"
    return None


def _per_1k(vph: float | None, followers: int | None) -> float | None:
    if vph is None or not followers:
        return None
    return vph / (followers / 1000.0)


def reel_velocity(session: Session, niche: str | None = None) -> list[dict]:
    """Reels with >=2 snapshots (velocity between the latest two) or a known posted_at.
    Sorted by views_per_hour desc."""
    out = []
    for r in load_reels(session, niche):
        v = _velocity(r)
        if v is None:
            continue
        vph, hours, method = v
        out.append({
            "code": r.code,
            "creator": r.creator,
            "niche": r.niche,
            "followers": r.followers,
            "views": r.views,
            "views_per_hour": round(vph, 3),
            "velocity_per_1k_followers": (
                round(_per_1k(vph, r.followers), 4) if _per_1k(vph, r.followers) is not None else None
            ),
            "hours_observed": round(hours, 3),
            "method": method,
        })
    out.sort(key=lambda d: d["views_per_hour"], reverse=True)
    return out


def velocity_vs_followers(session: Session, niche: str | None = None) -> list[dict]:
    """Scatter points for every reel whose creator follower count is known."""
    out = []
    for r in load_reels(session, niche):
        if r.followers is None:
            continue
        v = _velocity(r)
        out.append({
            "code": r.code,
            "creator": r.creator,
            "niche": r.niche,
            "followers": r.followers,
            "views": r.views,
            "multiple": round(r.multiple or 0.0, 3),
            "velocity": round(v[0], 3) if v else None,
            "bucket": follower_bucket(r.followers),
            "is_outlier": row_is_outlier(r),
            "format": r.format,
        })
    return out


def bucket_summary(session: Session, niche: str | None = None) -> list[dict]:
    """One row per follower bucket (all 5, in order): median views, outlier rate, top format.
    top_format = format with most outlier reels in the bucket, falling back to the most common format."""
    groups: dict[str, list[ReelRow]] = {b: [] for b in BUCKETS}
    for r in load_reels(session, niche):
        b = follower_bucket(r.followers)
        if b is not None:
            groups[b].append(r)
    out = []
    for b in BUCKETS:
        rows = groups[b]
        outl = [r for r in rows if row_is_outlier(r)]
        fmt_counts = Counter(r.format for r in outl if r.format) or Counter(r.format for r in rows if r.format)
        out.append({
            "bucket": b,
            "n_reels": len(rows),
            "n_creators": len({r.creator_id for r in rows}),
            "median_views": median(r.views for r in rows),
            "median_multiple": median(r.multiple for r in rows),
            "outlier_count": len(outl),
            "outlier_rate": round(len(outl) / len(rows), 4) if rows else 0.0,
            "top_format": fmt_counts.most_common(1)[0][0] if fmt_counts else None,
        })
    return out
