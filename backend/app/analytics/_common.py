"""Shared loaders/helpers for analytics. Internal module."""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Creator, CreatorSnapshot, Format, Reel, ReelLabel, ReelSnapshot

# Default outlier thresholds (mirror find_outliers defaults).
MIN_MULTIPLE = 10.0
SMALL_MAX_FOLLOWERS = 10_000
SMALL_MIN_VIEWS = 100_000

BUCKETS = ["<10K", "10–50K", "50–250K", "250K–1M", "1M+"]


def to_naive_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def iso(dt: datetime | None) -> str | None:
    dt = to_naive_utc(dt)
    return dt.isoformat() if dt is not None else None


def median(values) -> float | None:
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return float(statistics.median(vals))


def reel_url(code: str) -> str:
    return f"https://www.instagram.com/reel/{code}/"


def follower_bucket(followers: int | None) -> str | None:
    if followers is None:
        return None
    if followers < 10_000:
        return BUCKETS[0]
    if followers < 50_000:
        return BUCKETS[1]
    if followers < 250_000:
        return BUCKETS[2]
    if followers < 1_000_000:
        return BUCKETS[3]
    return BUCKETS[4]


def is_small(followers: int | None, max_followers: int = SMALL_MAX_FOLLOWERS) -> bool:
    return followers is not None and followers <= max_followers


def compute_multiple(views: int, creator_median: float | None) -> float:
    denom = creator_median if creator_median and creator_median > 0 else 1.0
    return float(views) / denom


def is_outlier(
    views: int,
    multiple: float,
    followers: int | None,
    min_multiple: float = MIN_MULTIPLE,
    small_creator_max_followers: int = SMALL_MAX_FOLLOWERS,
    small_creator_min_views: int = SMALL_MIN_VIEWS,
) -> bool:
    if multiple >= min_multiple:
        return True
    # Small-creator rule: big absolute views from a tiny account count even below min_multiple.
    return is_small(followers, small_creator_max_followers) and views >= small_creator_min_views


@dataclass
class ReelRow:
    reel_id: int
    code: str
    creator_id: int
    creator: str
    niche: str | None
    followers: int | None
    first_seen_at: datetime | None
    posted_at: datetime | None
    caption: str | None
    snapshots: list[tuple[datetime, int]] = field(default_factory=list)  # sorted ascending
    format_id: int | None = None
    format: str | None = None
    hook: str | None = None
    creator_median: float | None = None
    multiple: float | None = None

    @property
    def views(self) -> int:
        return self.snapshots[-1][1] if self.snapshots else 0

    @property
    def last_scraped_at(self) -> datetime | None:
        return self.snapshots[-1][0] if self.snapshots else None


def latest_followers(session: Session, creator_ids=None) -> dict[int, int | None]:
    """Latest non-null follower count per creator (None if never known)."""
    q = select(CreatorSnapshot.creator_id, CreatorSnapshot.scraped_at, CreatorSnapshot.id,
               CreatorSnapshot.followers)
    if creator_ids is not None:
        q = q.where(CreatorSnapshot.creator_id.in_(list(creator_ids)))
    best: dict[int, tuple] = {}
    for cid, ts, sid, fol in session.execute(q).all():
        if fol is None:
            continue
        key = (to_naive_utc(ts), sid)
        if cid not in best or key > best[cid][0]:
            best[cid] = (key, fol)
    return {cid: v[1] for cid, v in best.items()}


def load_reels(session: Session, niche: str | None = None, creator_id: int | None = None) -> list[ReelRow]:
    """Load every reel (with >=1 snapshot) plus creator, latest followers, label and all snapshots.

    Also fills creator_median (median of latest views over the creator's reels) and multiple.
    """
    q = select(Reel, Creator).join(Creator, Reel.creator_id == Creator.id)
    if niche:
        q = q.where(Creator.niche == niche)
    if creator_id is not None:
        q = q.where(Creator.id == creator_id)
    rows: dict[int, ReelRow] = {}
    for reel, creator in session.execute(q).all():
        rows[reel.id] = ReelRow(
            reel_id=reel.id,
            code=reel.code,
            creator_id=creator.id,
            creator=creator.username,
            niche=creator.niche,
            followers=None,
            first_seen_at=to_naive_utc(reel.first_seen_at),
            posted_at=to_naive_utc(reel.posted_at),
            caption=reel.caption,
        )
    if not rows:
        return []

    snap_q = (
        select(ReelSnapshot.reel_id, ReelSnapshot.scraped_at, ReelSnapshot.id, ReelSnapshot.views)
        .join(Reel, ReelSnapshot.reel_id == Reel.id)
        .join(Creator, Reel.creator_id == Creator.id)
    )
    if niche:
        snap_q = snap_q.where(Creator.niche == niche)
    if creator_id is not None:
        snap_q = snap_q.where(Creator.id == creator_id)
    raw: dict[int, list[tuple]] = {}
    for rid, ts, sid, views in session.execute(snap_q).all():
        if rid in rows and views is not None:
            raw.setdefault(rid, []).append((to_naive_utc(ts), sid, int(views)))
    for rid, snaps in raw.items():
        snaps.sort()
        rows[rid].snapshots = [(ts, v) for ts, _sid, v in snaps]

    lab_q = (
        select(ReelLabel.reel_id, ReelLabel.hook_text, Format.id, Format.name)
        .outerjoin(Format, ReelLabel.format_id == Format.id)
        .join(Reel, ReelLabel.reel_id == Reel.id)
        .join(Creator, Reel.creator_id == Creator.id)
    )
    if niche:
        lab_q = lab_q.where(Creator.niche == niche)
    if creator_id is not None:
        lab_q = lab_q.where(Creator.id == creator_id)
    for rid, hook, fid, fname in session.execute(lab_q).all():
        if rid in rows:
            rows[rid].hook = hook
            rows[rid].format_id = fid
            rows[rid].format = fname

    result = [r for r in rows.values() if r.snapshots]
    fol = latest_followers(session, {r.creator_id for r in result})
    by_creator: dict[int, list[int]] = {}
    for r in result:
        r.followers = fol.get(r.creator_id)
        by_creator.setdefault(r.creator_id, []).append(r.views)
    medians = {cid: median(v) for cid, v in by_creator.items()}
    for r in result:
        r.creator_median = medians[r.creator_id]
        r.multiple = compute_multiple(r.views, r.creator_median)
    return result


def row_is_outlier(r: ReelRow, **kw) -> bool:
    return is_outlier(r.views, r.multiple or 0.0, r.followers, **kw)
