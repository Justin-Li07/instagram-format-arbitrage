from datetime import timedelta

import pytest
from test_analytics_fixtures import T0, Builder, make_session

from app.analytics.formats import format_market, format_timeseries

NOW = T0 + timedelta(days=60)


def _add(b, creator, fmt, n, days_ago, views, prefix):
    for i in range(n):
        at = NOW - timedelta(days=days_ago)
        b.reel(creator, f"{prefix}{i}", [(at, views)], first_seen=at, fmt=fmt)


def _by_name(rows):
    return {r["format"]: r for r in rows}


def test_closing_status_triggers():
    s = make_session()
    b = Builder(s)
    c = b.creator("c", 50_000)
    _add(b, c, "Closing", 2, 21, 100_000, "PREV")  # previous 2 weeks: 2 reels, high views
    _add(b, c, "Closing", 3, 3, 10_000, "REC")  # last 2 weeks: 3 reels, low views
    row = _by_name(format_market(s, now=NOW))["Closing"]
    assert row["supply_recent"] == 3 and row["supply_prev"] == 2
    assert row["price_recent"] == 10_000 and row["price_prev"] == 100_000
    assert row["status"] == "closing"


def test_not_closing_when_price_rises():
    s = make_session()
    b = Builder(s)
    c = b.creator("c", 50_000)
    _add(b, c, "Rising", 2, 21, 10_000, "PREV")
    _add(b, c, "Rising", 3, 3, 100_000, "REC")
    assert _by_name(format_market(s, now=NOW))["Rising"]["status"] != "closing"


def test_new_status():
    s = make_session()
    b = Builder(s)
    c = b.creator("c", 50_000)
    _add(b, c, "TwoReels", 2, 40, 5_000, "TW")  # < 3 reels
    _add(b, c, "Fresh", 5, 5, 5_000, "FR")  # first seen within 14 days
    rows = _by_name(format_market(s, now=NOW))
    assert rows["TwoReels"]["status"] == "new"
    assert rows["Fresh"]["status"] == "new"


def test_price_supply_score_and_crowded_vs_opportunity():
    s = make_session()
    b = Builder(s)
    small = b.creator("small", 5_000)
    big = b.creator("big", 900_000)
    _add(b, big, "A", 8, 40, 1_000, "A")  # supply 1/wk, price 1000 -> crowded
    _add(b, small, "B", 3, 40, 50_000, "B")  # supply 3/8, price 50000 -> opportunity
    _add(b, big, "C", 4, 40, 5_000, "C")  # supply 0.5 = median -> opportunity
    rows = format_market(s, weeks=8, now=NOW)
    assert [r["format"] for r in rows] == ["B", "C", "A"]  # sorted by score
    by = _by_name(rows)
    a = by["A"]
    assert a["price"] == 1_000
    assert a["supply"] == pytest.approx(1.0)
    assert a["score"] == pytest.approx(500.0)
    assert a["n_reels"] == 8 and a["n_creators"] == 1
    assert a["status"] == "crowded"
    assert by["B"]["supply"] == pytest.approx(0.375)
    assert by["B"]["small_creator_share"] == 1.0
    assert by["B"]["status"] == "opportunity"
    assert by["C"]["status"] == "opportunity"


def test_supply_window_and_default_now():
    s = make_session()
    b = Builder(s)
    c = b.creator("c", 50_000)
    _add(b, c, "Old", 4, 100, 1_000, "OLD")  # outside 8 weeks
    _add(b, c, "Old", 2, 20, 1_000, "IN")
    # default "now" = newest scrape in data (NOW - 20d); the old reels are 80 days before that
    rows = _by_name(format_market(s, weeks=8, now=NOW))
    assert rows["Old"]["supply"] == pytest.approx(2 / 8)
    rows_default = _by_name(format_market(s, weeks=8))
    assert rows_default["Old"]["supply"] == pytest.approx(2 / 8)
    assert format_market(make_session()) == []


def test_niche_filter():
    s = make_session()
    b = Builder(s)
    e = b.creator("e", 1_000, niche="engineering")
    u = b.creator("u", 1_000, niche="university-life")
    _add(b, e, "Eng", 3, 30, 1_000, "E")
    _add(b, u, "Uni", 3, 30, 1_000, "U")
    assert {r["format"] for r in format_market(s, niche="engineering", now=NOW)} == {"Eng"}


def test_format_timeseries_weekly_with_gap():
    s = make_session()
    b = Builder(s)
    c = b.creator("c", 50_000)
    w1 = T0  # 2026-11-01 is a Sunday -> week starting Mon 2026-10-26
    b.reel(c, "T1", [(w1, 100), (w1 + timedelta(days=14), 300)], fmt="TS")
    b.reel(c, "T2", [(w1, 200)], fmt="TS")
    b.reel(c, "T3", [(w1 + timedelta(days=14), 1_000)], fmt="TS")
    fid = b.fmt("TS").id
    pts = format_timeseries(s, fid)
    assert [p["week"] for p in pts] == ["2026-10-26", "2026-11-02", "2026-11-09"]
    assert pts[0] == {"week": "2026-10-26", "median_views": 150.0, "new_posts": 2}
    assert pts[1] == {"week": "2026-11-02", "median_views": None, "new_posts": 0}
    assert pts[2] == {"week": "2026-11-09", "median_views": 650.0, "new_posts": 1}
    assert format_timeseries(s, 9999) == []
