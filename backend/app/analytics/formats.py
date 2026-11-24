"""Formats as markets: PRICE = median views per reel, SUPPLY = new reels per week."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics._common import ReelRow, is_small, iso, load_reels, median, to_naive_utc
from app.db.models import Format

NEW_MIN_REELS = 3
NEW_WINDOW = timedelta(days=14)
WINDOW = timedelta(days=14)  # closing compares last 2 weeks vs previous 2


def _reference_now(rows: list[ReelRow], now: datetime | None) -> datetime:
    """Anchor time windows to the newest scrape in the data (so historical imports still work)."""
    if now is not None:
        return to_naive_utc(now)
    times = [r.last_scraped_at for r in rows if r.last_scraped_at] + [r.first_seen_at for r in rows if r.first_seen_at]
    return max(times) if times else datetime.now(timezone.utc).replace(tzinfo=None)


def _in(r: ReelRow, start: datetime, end: datetime) -> bool:
    return r.first_seen_at is not None and start < r.first_seen_at <= end


def format_market(session: Session, niche: str | None = None, weeks: int = 8,
                  now: datetime | None = None) -> list[dict]:
    """Per Format: price, supply, score = price/(supply+1), status. Sorted by score desc.

    status: "new" (<3 reels or first seen within 14 days) > "closing" (supply up AND price down,
    last 2 weeks vs previous 2, by reel first_seen_at) > "crowded" (supply above niche median
    AND score below niche median) > "opportunity".
    """
    rows = load_reels(session, niche)
    ref = _reference_now(rows, now)
    weeks = max(int(weeks), 1)
    by_fmt: dict[int, list[ReelRow]] = {}
    for r in rows:
        if r.format_id is not None:
            by_fmt.setdefault(r.format_id, []).append(r)
    if not by_fmt:
        return []
    fmts = {f.id: f for f in session.execute(select(Format).where(Format.id.in_(list(by_fmt)))).scalars()}

    supply_start = ref - timedelta(weeks=weeks)
    recent_start, prev_start = ref - WINDOW, ref - 2 * WINDOW
    out = []
    for fid, reels in by_fmt.items():
        f = fmts.get(fid)
        price = median(r.views for r in reels) or 0.0
        supply = sum(1 for r in reels if _in(r, supply_start, ref)) / weeks
        recent = [r for r in reels if _in(r, recent_start, ref)]
        prev = [r for r in reels if _in(r, prev_start, recent_start)]
        first_seen = min((r.first_seen_at for r in reels if r.first_seen_at), default=None)
        out.append({
            "format_id": fid,
            "format": f.name if f else None,
            "description": f.description if f else None,
            "style": f.style if f else None,
            "price": price,
            "supply": round(supply, 4),
            "n_reels": len(reels),
            "n_creators": len({r.creator_id for r in reels}),
            "small_creator_share": round(sum(1 for r in reels if is_small(r.followers)) / len(reels), 4),
            "score": round(price / (supply + 1), 3),
            "first_seen_at": iso(first_seen),
            "supply_recent": len(recent),
            "supply_prev": len(prev),
            "price_recent": median(r.views for r in recent),
            "price_prev": median(r.views for r in prev),
            "_first_seen": first_seen,
        })

    med_supply = median(d["supply"] for d in out)
    med_score = median(d["score"] for d in out)
    for d in out:
        first_seen = d.pop("_first_seen")
        if d["n_reels"] < NEW_MIN_REELS or (first_seen is not None and first_seen > ref - NEW_WINDOW):
            status = "new"
        elif (d["supply_recent"] > d["supply_prev"] and d["price_recent"] is not None
              and d["price_prev"] is not None and d["price_recent"] < d["price_prev"]):
            status = "closing"
        elif d["supply"] > med_supply and d["score"] < med_score:
            status = "crowded"
        else:
            status = "opportunity"
        d["status"] = status
    out.sort(key=lambda d: d["score"], reverse=True)
    return out


def _week_start(dt: datetime) -> datetime:
    d = dt - timedelta(days=dt.weekday())
    return datetime(d.year, d.month, d.day)


def format_timeseries(session: Session, format_id: int, niche: str | None = None) -> list[dict]:
    """Weekly {week (Monday ISO date), median_views, new_posts} for one format.

    median_views = median over the format's reels of each reel's latest snapshot taken in that week
    (the format's "price" as observed that week); new_posts = reels first seen that week.
    Gaps between the first and last week are filled (median_views None, new_posts 0).
    """
    reels = [r for r in load_reels(session, niche) if r.format_id == format_id]
    if not reels:
        return []
    views_by_week: dict[datetime, dict[int, tuple[datetime, int]]] = {}
    posts_by_week: dict[datetime, int] = {}
    for r in reels:
        for ts, v in r.snapshots:
            wk = _week_start(ts)
            cur = views_by_week.setdefault(wk, {}).get(r.reel_id)
            if cur is None or ts >= cur[0]:
                views_by_week[wk][r.reel_id] = (ts, v)
        if r.first_seen_at is not None:
            wk = _week_start(r.first_seen_at)
            posts_by_week[wk] = posts_by_week.get(wk, 0) + 1
    all_weeks = set(views_by_week) | set(posts_by_week)
    wk, last = min(all_weeks), max(all_weeks)
    out = []
    while wk <= last:
        vals = [v for _ts, v in views_by_week.get(wk, {}).values()]
        out.append({"week": wk.date().isoformat(), "median_views": median(vals),
                    "new_posts": posts_by_week.get(wk, 0)})
        wk += timedelta(weeks=1)
    return out
