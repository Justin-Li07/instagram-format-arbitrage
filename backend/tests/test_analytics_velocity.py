from datetime import timedelta

import pytest
from test_analytics_fixtures import T0, Builder, make_session

from app.analytics.velocity import bucket_summary, reel_velocity, velocity_vs_followers


def test_velocity_two_snapshots_24h_apart():
    s = make_session()
    b = Builder(s)
    c = b.creator("v", 5_000)
    b.reel(c, "V1", [(T0, 1_000), (T0 + timedelta(hours=24), 25_000)])
    rows = reel_velocity(s)
    assert len(rows) == 1
    r = rows[0]
    assert r["code"] == "V1"
    assert r["views"] == 25_000
    assert r["hours_observed"] == pytest.approx(24.0)
    assert r["views_per_hour"] == pytest.approx(1_000.0)  # (25000-1000)/24
    assert r["velocity_per_1k_followers"] == pytest.approx(200.0)  # 1000 / 5
    assert r["method"] == "snapshots"


def test_velocity_uses_latest_two_snapshots():
    s = make_session()
    b = Builder(s)
    c = b.creator("v", 10_000)
    b.reel(c, "V3", [(T0, 0), (T0 + timedelta(hours=10), 10_000), (T0 + timedelta(hours=12), 10_400)])
    r = reel_velocity(s)[0]
    assert r["views_per_hour"] == pytest.approx(200.0)
    assert r["hours_observed"] == pytest.approx(2.0)


def test_velocity_from_posted_at_and_single_snapshot_skipped():
    s = make_session()
    b = Builder(s)
    c = b.creator("p", None)
    b.reel(c, "POSTED", [(T0, 5_000)], posted_at=T0 - timedelta(hours=10))
    b.reel(c, "ONESNAP", [(T0, 9_999)])
    rows = reel_velocity(s)
    assert [r["code"] for r in rows] == ["POSTED"]
    assert rows[0]["views_per_hour"] == pytest.approx(500.0)
    assert rows[0]["velocity_per_1k_followers"] is None
    assert rows[0]["method"] == "posted_at"


def test_velocity_vs_followers_buckets():
    s = make_session()
    b = Builder(s)
    cases = {"a": 7_482, "b": 10_000, "c": 60_000, "d": 999_999, "e": 1_000_000}
    for u, f in cases.items():
        c = b.creator(u, f)
        b.reel(c, f"R{u}", [(T0, 100), (T0 + timedelta(hours=1), 200)])
    nobody = b.creator("nofollow", None)
    b.reel(nobody, "RX", [(T0, 100)])
    pts = {p["creator"]: p for p in velocity_vs_followers(s)}
    assert "nofollow" not in pts
    assert pts["a"]["bucket"] == "<10K"
    assert pts["b"]["bucket"] == "10–50K"
    assert pts["c"]["bucket"] == "50–250K"
    assert pts["d"]["bucket"] == "250K–1M"
    assert pts["e"]["bucket"] == "1M+"
    assert pts["a"]["velocity"] == pytest.approx(100.0)
    assert pts["a"]["multiple"] == 1.0
    assert {"followers", "views", "multiple", "velocity", "code", "creator", "bucket"} <= set(pts["a"])


def test_bucket_summary():
    s = make_session()
    b = Builder(s)
    small = b.creator("small", 5_000)
    b.reel(small, "S1", [(T0, 200_000)], fmt="Listicle")  # small-creator outlier
    b.reel(small, "S2", [(T0, 2_000)], fmt="Vlog")
    big = b.creator("big", 2_000_000)
    b.reel(big, "B1", [(T0, 1_000_000)], fmt="Vlog")
    rows = bucket_summary(s)
    assert [r["bucket"] for r in rows] == ["<10K", "10–50K", "50–250K", "250K–1M", "1M+"]
    by = {r["bucket"]: r for r in rows}
    assert by["<10K"]["n_reels"] == 2
    assert by["<10K"]["median_views"] == 101_000
    assert by["<10K"]["outlier_rate"] == 0.5
    assert by["<10K"]["top_format"] == "Listicle"
    assert by["1M+"]["outlier_rate"] == 0.0
    assert by["1M+"]["top_format"] == "Vlog"  # fallback: most common format
    assert by["10–50K"]["n_reels"] == 0 and by["10–50K"]["median_views"] is None
