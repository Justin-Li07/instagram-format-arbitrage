"""Import scraper output (scan-*.jsonl) and labels (labels-*.jsonl) into the DB."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Creator,
    CreatorSnapshot,
    Format,
    Reel,
    ReelLabel,
    ReelSnapshot,
    ScrapeRun,
    utcnow,
)
from app.embeddings.embedder import upsert_hook_embedding
from app.ingest.parse import parse_count

log = logging.getLogger(__name__)

_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _naive_utc(dt: datetime) -> datetime:
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _parse_dt(value) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return _naive_utc(value)
    try:
        return _naive_utc(datetime.fromisoformat(str(value).replace("Z", "+00:00")))
    except ValueError:
        return None


def source_for_path(path: str | Path) -> str:
    """Stable source id: 'data/<niche>/<file>' when under a data/ folder, else absolute posix path."""
    p = Path(path).resolve()
    if p.parent.parent.name == "data":
        return f"data/{p.parent.name}/{p.name}"
    return p.as_posix()


def date_from_filename(path: str | Path) -> datetime | None:
    m = _DATE_RE.search(Path(path).name)
    return datetime.strptime(m.group(1), "%Y-%m-%d") if m else None


def read_jsonl(path: str | Path) -> list[dict]:
    records: list[dict] = []
    with open(path, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                log.warning("%s:%d: skipping invalid JSON line", path, lineno)
    return records


def _split_reel_entry(entry) -> tuple[str, int | None] | None:
    if isinstance(entry, dict):
        code = entry.get("code")
        views = parse_count(entry.get("views"))
    else:
        parts = str(entry).strip().split(None, 1)
        if not parts:
            return None
        code = parts[0]
        views = parse_count(parts[1]) if len(parts) > 1 else None
    if not code:
        return None
    return code, views


def import_scan_records(
    session: Session,
    records: list[dict],
    niche: str,
    scraped_at: datetime,
    source: str = "api",
    run: ScrapeRun | None = None,
) -> ScrapeRun:
    """Add one ScrapeRun plus a snapshot per creator and per reel. Never overwrites snapshots.

    A reel/creator that already has a snapshot at exactly this `scraped_at` is not snapshotted again.
    Pass `run` to add records to an existing run (used when a scan file grew after it was imported).
    """
    scraped_at = _naive_utc(scraped_at)
    if run is None:
        # started_at = when the scrape happened (== scraped_at of every snapshot in this run)
        run = ScrapeRun(niche=niche, source=source, started_at=scraped_at, creators_count=0, reels_count=0)
        session.add(run)
        session.flush()

    seen_creators: set[int] = set()
    seen_reels: set[int] = set()

    for rec in records:
        username = (rec.get("u") or rec.get("username") or "").strip().lstrip("@")
        if not username:
            continue
        creator = session.scalar(select(Creator).where(Creator.username == username))
        if creator is None:
            creator = Creator(username=username, niche=niche, first_seen_at=scraped_at, last_seen_at=scraped_at)
            session.add(creator)
            session.flush()
        else:
            if creator.niche is None:
                creator.niche = niche
            if scraped_at < creator.first_seen_at:
                creator.first_seen_at = scraped_at
            if scraped_at > creator.last_seen_at:
                creator.last_seen_at = scraped_at

        if creator.id not in seen_creators:
            seen_creators.add(creator.id)
            dup = session.scalar(
                select(CreatorSnapshot.id).where(
                    CreatorSnapshot.creator_id == creator.id, CreatorSnapshot.scraped_at == scraped_at
                )
            )
            if dup is None:
                session.add(
                    CreatorSnapshot(
                        creator_id=creator.id,
                        scraped_at=scraped_at,
                        followers=parse_count(rec.get("f")),
                        scrape_run_id=run.id,
                    )
                )

        for entry in rec.get("r") or []:
            parsed = _split_reel_entry(entry)
            if parsed is None:
                continue
            code, views = parsed
            if views is None:
                continue
            reel = session.scalar(select(Reel).where(Reel.code == code))
            if reel is None:
                reel = Reel(code=code, creator_id=creator.id, first_seen_at=scraped_at)
                session.add(reel)
                session.flush()
            elif scraped_at < reel.first_seen_at:
                reel.first_seen_at = scraped_at
            if reel.id in seen_reels:
                continue
            seen_reels.add(reel.id)
            dup = session.scalar(
                select(ReelSnapshot.id).where(ReelSnapshot.reel_id == reel.id, ReelSnapshot.scraped_at == scraped_at)
            )
            if dup is None:
                session.add(ReelSnapshot(reel_id=reel.id, scraped_at=scraped_at, views=views, scrape_run_id=run.id))

    run.creators_count = len(seen_creators)
    run.reels_count = len(seen_reels)
    session.commit()
    return run


def import_scan_file(
    session: Session,
    path: str,
    niche: str | None = None,
    scraped_at: datetime | None = None,
) -> ScrapeRun:
    """Import a scan-*.jsonl file.

    Idempotent: the same file at the same scraped_at returns the existing run, unless the file now
    has more creators than that run recorded (scrapers append while running). Then the file is
    re-read into the same run; already-stored snapshots are not duplicated.
    """
    p = Path(path)
    niche = niche or p.resolve().parent.name
    if scraped_at is None:
        scraped_at = date_from_filename(p) or datetime.fromtimestamp(p.stat().st_mtime, timezone.utc)
    scraped_at = _naive_utc(scraped_at)
    source = source_for_path(p)

    existing = session.scalar(
        select(ScrapeRun).where(ScrapeRun.source == source, ScrapeRun.started_at == scraped_at).limit(1)
    )
    records = read_jsonl(p)
    if existing is not None:
        usernames = {(r.get("u") or r.get("username") or "").strip().lstrip("@") for r in records}
        usernames.discard("")
        if len(usernames) <= existing.creators_count:
            return existing
        return import_scan_records(
            session, records, niche=niche, scraped_at=scraped_at, source=source, run=existing
        )
    return import_scan_records(session, records, niche=niche, scraped_at=scraped_at, source=source)


def import_labels(session: Session, records: list[dict], labeled_by: str = "agent") -> int:
    """Upsert Format + ReelLabel, fill Reel caption/duration/posted_at, embed the hook.

    A record may carry "paid": true/false to flag a "Paid partnership" reel (excluded from all
    analytics); such a record needs no format. Records whose reel code is not in the DB yet are
    skipped. Returns the number of labels upserted.
    """
    count = 0
    for rec in records:
        code = rec.get("code")
        fmt_name = (rec.get("format") or "").strip()
        if not code or (not fmt_name and "paid" not in rec):
            continue
        reel = session.scalar(select(Reel).where(Reel.code == code))
        if reel is None:
            log.warning("labels: reel %s not imported yet; skipping", code)
            continue
        if "paid" in rec:
            reel.is_paid_partnership = bool(rec["paid"])
        if not fmt_name:
            continue

        fmt = session.scalar(select(Format).where(Format.name == fmt_name))
        if fmt is None:
            fmt = Format(name=fmt_name, description=rec.get("format_description"), style=rec.get("style"))
            session.add(fmt)
            session.flush()
        elif fmt.style is None and rec.get("style"):
            fmt.style = rec.get("style")

        if rec.get("caption") is not None:
            reel.caption = rec["caption"]
        if rec.get("duration_s") is not None:
            reel.duration_s = float(rec["duration_s"])
        posted = _parse_dt(rec.get("posted_at"))
        if posted is not None:
            reel.posted_at = posted

        label = session.get(ReelLabel, reel.id)
        if label is None:
            label = ReelLabel(reel_id=reel.id)
            session.add(label)
        label.format_id = fmt.id
        label.hook_text = rec.get("hook")
        label.on_screen = rec.get("on_screen")
        label.style = rec.get("style")
        label.labeled_at = utcnow()
        label.labeled_by = rec.get("labeled_by") or labeled_by

        hook = rec.get("hook")
        if hook:
            upsert_hook_embedding(session, reel.id, hook)
        count += 1

    session.commit()
    return count


def import_labels_file(session: Session, path: str) -> int:
    return import_labels(session, read_jsonl(path))
