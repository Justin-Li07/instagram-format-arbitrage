"""End-to-end API tests: ingest -> analytics -> labels -> formats/hooks.

Uses a throwaway SQLite file and overrides the `get_session` dependency so
the real backend/formatarb.db is never touched.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

_TMP = Path(tempfile.mkdtemp(prefix="fa_api_test_"))
os.environ.setdefault("FA_DB_URL", f"sqlite:///{(_TMP / 'env.db').as_posix()}")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

import app.main as main_mod  # noqa: E402
from app.db.models import Base  # noqa: E402
from app.db.session import get_session  # noqa: E402

SCAN_RECORDS = [
    # one huge outlier vs a small median
    {"u": "tiny.eng", "f": "7,482", "r": ["AAAhit00001 1.2M", "AAAlow00002 5,181", "AAAlow00003 4.2K", "AAAlow00004 6K", "AAAlow00005 3,900"]},
    {"u": "mid.eng", "f": "22.7K", "r": ["BBBreel0001 40K", "BBBreel0002 35.5K", "BBBreel0003 51K", "BBBhit00004 2.4M"]},
    {"u": "big.eng", "f": "1.3M", "r": ["CCCreel0001 900K", "CCCreel0002 1.1M", "CCCreel0003 1M"]},
]

LABELS = [
    {"code": "AAAhit00001", "format": "Text-over-B-roll + caption list",
     "hook": "5 engineering certifications you can start TONIGHT", "caption": "save this",
     "duration_s": 6.2, "on_screen": "solo creator", "style": "text-over-broll", "posted_at": None},
    {"code": "BBBhit00004", "format": "Text-over-B-roll + caption list",
     "hook": "3 free engineering courses that beat a degree", "caption": None,
     "duration_s": 7.0, "on_screen": "solo creator", "style": "text-over-broll", "posted_at": None},
    {"code": "CCCreel0002", "format": "Talking head rant",
     "hook": "nobody tells you this about your first internship", "caption": None,
     "duration_s": 31.5, "on_screen": "face to camera", "style": "talking-head", "posted_at": None},
]


@pytest.fixture(scope="module")
def client():
    engine = create_engine(
        f"sqlite:///{(_TMP / 'api.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def _override():
        s = TestSession()
        try:
            yield s
        finally:
            s.close()

    calls = []
    orig_init = main_mod.init_db
    main_mod.init_db = lambda: calls.append(1)
    main_mod.app.dependency_overrides[get_session] = _override
    try:
        with TestClient(main_mod.app) as c:
            assert calls, "init_db() should run on startup"
            yield c
    finally:
        main_mod.app.dependency_overrides.clear()
        main_mod.init_db = orig_init
        engine.dispose()


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_cors_preflight(client):
    r = client.options(
        "/api/health",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_ingest_scan(client):
    r = client.post(
        "/api/ingest/scan",
        json={"niche": "engineering", "scraped_at": "2026-11-24T12:00:00", "records": SCAN_RECORDS},
    )
    assert r.status_code == 201, r.text
    run = r.json()
    assert run["niche"] == "engineering"
    assert run["source"] == "api"
    assert run["creators_count"] == 3
    assert run["reels_count"] == 12

    # a second scrape adds history
    r2 = client.post(
        "/api/ingest/scan",
        json={"niche": "engineering", "scraped_at": "2026-11-25T12:00:00",
              "records": [{"u": "tiny.eng", "f": "8.1K", "r": ["AAAhit00001 1.5M"]}]},
    )
    assert r2.status_code == 201, r2.text

    runs = client.get("/api/runs").json()
    assert len(runs) == 2


def test_niches(client):
    r = client.get("/api/niches")
    assert r.status_code == 200
    by = {n["niche"]: n for n in r.json()}
    assert set(by) == {"engineering", "university-life", "startups-tech", "growth-viral"}
    assert by["engineering"]["creators"] == 3
    assert by["engineering"]["reels"] == 12
    assert by["engineering"]["last_scraped_at"].startswith("2026-11-25")
    assert by["growth-viral"]["creators"] == 0


def test_outliers(client):
    r = client.get("/api/outliers", params={"niche": "engineering", "min_multiple": 10})
    assert r.status_code == 200, r.text
    codes = {o["code"] for o in r.json()}
    assert "AAAhit00001" in codes
    assert "CCCreel0002" not in codes
    hit = next(o for o in r.json() if o["code"] == "AAAhit00001")
    assert hit["creator"] == "tiny.eng"
    assert hit["views"] == 1_500_000  # latest snapshot
    assert hit["multiple"] >= 10


def test_creator_detail(client):
    r = client.get("/api/creators/tiny.eng")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["username"] == "tiny.eng"
    assert [h["followers"] for h in body["follower_history"]] == [7482, 8100]
    lst = client.get("/api/creators", params={"niche": "engineering"})
    assert lst.status_code == 200
    assert {c["username"] for c in lst.json()} == {"tiny.eng", "mid.eng", "big.eng"}


def test_reel_detail(client):
    r = client.get("/api/reels/AAAhit00001")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["creator"]["username"] == "tiny.eng"
    assert body["creator"]["followers"] == 8100
    assert [s["views"] for s in body["snapshots"]] == [1_200_000, 1_500_000]
    assert body["views"] == 1_500_000
    assert body["label"] is None
    assert body["url"].endswith("/reel/AAAhit00001/")


def test_velocity(client):
    assert client.get("/api/velocity", params={"niche": "engineering"}).status_code == 200
    assert client.get("/api/velocity/buckets").status_code == 200


def test_labels_then_formats_and_hooks(client):
    r = client.post("/api/ingest/labels", json={"records": LABELS})
    assert r.status_code == 200, r.text
    assert r.json()["imported"] == 3

    reel = client.get("/api/reels/AAAhit00001").json()
    assert reel["label"]["format"] == "Text-over-B-roll + caption list"
    assert reel["caption"] == "save this"

    r = client.get("/api/formats", params={"niche": "engineering"})
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) == 2
    assert all("score" in row and "status" in row and row["format"] for row in rows)
    assert {row["format_id"] for row in rows} >= {1}

    fid = reel["label"]["format_id"]
    ts = client.get(f"/api/formats/{fid}/timeseries")
    assert ts.status_code == 200, ts.text

    r = client.get("/api/hooks/similar", params={"text": "engineering certifications to start tonight", "k": 3})
    assert r.status_code == 200, r.text
    sims = r.json()
    assert 1 <= len(sims) <= 3
    assert sims[0]["code"] == "AAAhit00001"
    assert sims[0]["score"] >= sims[-1]["score"]

    r = client.get("/api/hooks/similar", params={"code": "AAAhit00001", "k": 5})
    assert r.status_code == 200, r.text

    assert client.get("/api/hooks", params={"niche": "engineering"}).status_code == 200
