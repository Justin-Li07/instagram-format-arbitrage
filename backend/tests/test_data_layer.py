from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db.models import (
    Base,
    Creator,
    CreatorSnapshot,
    Format,
    HookEmbedding,
    Reel,
    ReelLabel,
    ReelSnapshot,
    ScrapeRun,
)
from app.embeddings.embedder import HashedNgramEmbedder, get_embedder, similar_hooks
from app.ingest.importer import import_labels, import_scan_file, import_scan_records
from app.ingest.parse import parse_count

REAL_SCAN = Path(__file__).resolve().parents[2] / "data" / "engineering" / "scan-2026-11-24.jsonl"

RECORDS = [
    {"u": "alice", "f": "7,482", "r": ["AAA111 34.4M", "AAA222 55.8K", "AAA333 5,181"]},
    {"u": "bob", "f": None, "r": ["BBB111 1.3M", "BBB222 900"]},
]


@pytest.fixture()
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def count(session, model) -> int:
    return session.scalar(select(func.count()).select_from(model))


@pytest.fixture()
def scan_file(tmp_path) -> Path:
    d = tmp_path / "data" / "engineering"
    d.mkdir(parents=True)
    p = d / "scan-2026-11-20.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in RECORDS) + "\n", encoding="utf-8")
    return p


# ---- parse_count -------------------------------------------------------------

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("5,181", 5181),
        ("22.7K", 22700),
        ("1.3M", 1_300_000),
        ("34.4M", 34_400_000),
        ("107K", 107_000),
        ("900", 900),
        ("2M", 2_000_000),
        ("1,234,567", 1_234_567),
        ("12.7k", 12700),
        (" 55.8K ", 55800),
        (None, None),
        ("", None),
        ("n/a", None),
        (42, 42),
    ],
)
def test_parse_count(raw, expected):
    assert parse_count(raw) == expected


# ---- scan import -------------------------------------------------------------

def test_import_scan_file_basic(session, scan_file):
    run = import_scan_file(session, str(scan_file))
    assert run.niche == "engineering"
    assert run.source == "data/engineering/scan-2026-11-20.jsonl"
    assert run.creators_count == 2 and run.reels_count == 5
    assert run.started_at == datetime(2026, 11, 20)
    alice = session.scalar(select(Creator).where(Creator.username == "alice"))
    snap = session.scalar(select(CreatorSnapshot).where(CreatorSnapshot.creator_id == alice.id))
    assert snap.followers == 7482
    bob = session.scalar(select(Creator).where(Creator.username == "bob"))
    assert session.scalar(select(CreatorSnapshot.followers).where(CreatorSnapshot.creator_id == bob.id)) is None
    views = session.scalar(
        select(ReelSnapshot.views).join(Reel).where(Reel.code == "AAA111")
    )
    assert views == 34_400_000


def test_import_twice_same_row_counts(session, scan_file):
    run1 = import_scan_file(session, str(scan_file))
    counts1 = [count(session, m) for m in (ScrapeRun, Creator, CreatorSnapshot, Reel, ReelSnapshot)]
    run2 = import_scan_file(session, str(scan_file))
    counts2 = [count(session, m) for m in (ScrapeRun, Creator, CreatorSnapshot, Reel, ReelSnapshot)]
    assert run1.id == run2.id
    assert counts1 == counts2 == [1, 2, 2, 5, 5]


def test_two_scrapes_two_snapshots_per_reel(session, scan_file):
    import_scan_file(session, str(scan_file), scraped_at=datetime(2026, 11, 20, 9))
    import_scan_file(session, str(scan_file), scraped_at=datetime(2026, 11, 21, 9))
    assert count(session, ScrapeRun) == 2
    assert count(session, Reel) == 5
    per_reel = session.execute(
        select(ReelSnapshot.reel_id, func.count()).group_by(ReelSnapshot.reel_id)
    ).all()
    assert len(per_reel) == 5 and all(n == 2 for _, n in per_reel)
    assert count(session, CreatorSnapshot) == 4


def test_import_scan_records_api(session):
    t1, t2 = datetime(2026, 11, 1), datetime(2026, 11, 2)
    import_scan_records(session, RECORDS, niche="startups-tech", scraped_at=t1)
    run = import_scan_records(session, RECORDS, niche="startups-tech", scraped_at=t2)
    assert run.source == "api"
    reel = session.scalar(select(Reel).where(Reel.code == "BBB111"))
    assert reel.first_seen_at == t1
    assert len(reel.snapshots) == 2


@pytest.mark.skipif(not REAL_SCAN.exists(), reason="real sample data missing")
def test_import_real_file(session):
    run = import_scan_file(session, str(REAL_SCAN))
    assert run.creators_count == 34
    assert run.reels_count > 100
    again = import_scan_file(session, str(REAL_SCAN))
    assert again.id == run.id
    assert count(session, ReelSnapshot) == run.reels_count


# ---- labels + embeddings -----------------------------------------------------

LABELS = [
    {"code": "AAA111", "format": "Text-over-B-roll + caption list",
     "hook": "5 engineering certifications you can start TONIGHT", "caption": "certs", "duration_s": 6.2,
     "on_screen": "solo creator", "style": "text-over-broll", "posted_at": "2026-11-10T12:00:00Z"},
    {"code": "AAA222", "format": "Day in the life",
     "hook": "a day in my life as a mechanical engineering student", "caption": None, "duration_s": 30,
     "on_screen": "solo creator", "style": "vlog", "posted_at": None},
    {"code": "BBB111", "format": "Text-over-B-roll + caption list",
     "hook": "why I quit my startup after raising money", "caption": None, "duration_s": None,
     "on_screen": "talking head", "style": "talking-head", "posted_at": None},
]


def test_labels_import(session, scan_file):
    import_scan_file(session, str(scan_file))
    n = import_labels(session, LABELS + [{"code": "NOPE", "format": "X", "hook": "missing reel"}])
    assert n == 3
    assert count(session, Format) == 2
    assert count(session, ReelLabel) == 3
    assert count(session, HookEmbedding) == 3
    reel = session.scalar(select(Reel).where(Reel.code == "AAA111"))
    assert reel.caption == "certs" and reel.duration_s == 6.2
    assert reel.posted_at == datetime(2026, 11, 10, 12)
    assert reel.label.format.name == "Text-over-B-roll + caption list"
    emb = session.get(HookEmbedding, reel.id)
    vec = np.frombuffer(emb.vector, dtype=np.float32)
    assert emb.dim == vec.shape[0] == get_embedder().dim
    assert abs(float(np.linalg.norm(vec)) - 1.0) < 1e-4
    # re-import is an upsert
    assert import_labels(session, LABELS) == 3
    assert (count(session, Format), count(session, ReelLabel), count(session, HookEmbedding)) == (2, 3, 3)


def test_similar_hooks_most_similar_first(session, scan_file):
    import_scan_file(session, str(scan_file))
    import_labels(session, LABELS)
    res = similar_hooks(session, text="engineering certifications to start tonight", k=3)
    assert len(res) == 3
    assert res[0][0].code == "AAA111"
    scores = [s for _, _, s in res]
    assert scores == sorted(scores, reverse=True)
    by_code = similar_hooks(session, reel_code="AAA111", k=5)
    assert all(r.code != "AAA111" for r, _, _ in by_code)
    assert len(by_code) == 2


def test_hashed_fallback_embedder():
    e = HashedNgramEmbedder()
    m = e.embed(["hello world", "hello world", "totally different"])
    assert m.shape == (3, 384) and m.dtype == np.float32
    assert np.allclose(np.linalg.norm(m, axis=1), 1.0, atol=1e-5)
    assert np.allclose(m[0], m[1])
    assert float(m[0] @ m[2]) < 0.9
