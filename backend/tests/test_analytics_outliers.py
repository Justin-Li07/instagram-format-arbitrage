from datetime import timedelta

from test_analytics_fixtures import T0, Builder, make_session

from app.analytics.outliers import find_outliers


def _codes(rows):
    return {r["code"] for r in rows}


def test_small_creator_flagged_below_10x():
    s = make_session()
    b = Builder(s)
    c = b.creator("tiny", 7_482)
    # Creator median ~454K, so the multiple is ~1x, yet the small-creator rule flags it.
    b.reel(c, "SMALL1", [(T0, 454_000)], fmt="Talking head", hook="nobody tells you this")
    b.reel(c, "SMALL2", [(T0, 400_000)])
    b.reel(c, "SMALL3", [(T0, 500_000)])
    b.reel(c, "SMALL4", [(T0, 50_000)])  # small creator but under 100K views -> not flagged
    rows = find_outliers(s)
    by = {r["code"]: r for r in rows}
    assert "SMALL1" in by
    o = by["SMALL1"]
    assert o["is_small_creator"] is True
    assert o["followers"] == 7_482
    assert o["views"] == 454_000
    assert o["multiple"] < 10
    assert o["format"] == "Talking head" and o["hook"] == "nobody tells you this"
    assert o["url"] == "https://www.instagram.com/reel/SMALL1/"
    assert "SMALL4" not in by


def test_reel_at_10x_median_flagged_and_9x_not():
    s = make_session()
    b = Builder(s)
    c = b.creator("mid", 200_000)
    for i in range(4):
        b.reel(c, f"BASE{i}", [(T0, 1_000)])
    b.reel(c, "TENX", [(T0, 10_000)])
    rows = find_outliers(s)
    assert _codes(rows) == {"TENX"}
    assert rows[0]["creator_median"] == 1_000
    assert rows[0]["multiple"] == 10.0
    assert rows[0]["is_small_creator"] is False

    c2 = b.creator("mid2", 200_000)
    for i in range(4):
        b.reel(c2, f"B2_{i}", [(T0, 1_000)])
    b.reel(c2, "NINEX", [(T0, 9_000)])
    assert "NINEX" not in _codes(find_outliers(s))


def test_uses_latest_snapshot():
    s = make_session()
    b = Builder(s)
    c = b.creator("grower", 500_000)
    for i in range(4):
        b.reel(c, f"G{i}", [(T0, 1_000)])
    # First scrape 1K (not an outlier), latest scrape 50K -> outlier.
    b.reel(c, "LATE", [(T0, 1_000), (T0 + timedelta(days=2), 50_000)])
    rows = find_outliers(s)
    assert _codes(rows) == {"LATE"}
    assert rows[0]["views"] == 50_000


def test_big_creator_big_views_not_flagged_without_multiple():
    s = make_session()
    b = Builder(s)
    c = b.creator("big", 2_000_000)
    b.reel(c, "B1", [(T0, 900_000)])
    b.reel(c, "B2", [(T0, 1_000_000)])
    assert find_outliers(s) == []


def test_niche_filter_limit_and_sorting():
    s = make_session()
    b = Builder(s)
    for niche, mult in [("engineering", 20), ("startups-tech", 50)]:
        c = b.creator(f"u-{niche}", 300_000, niche=niche)
        for i in range(3):
            b.reel(c, f"{niche}-{i}", [(T0, 1_000)])
        b.reel(c, f"{niche}-hit", [(T0, 1_000 * mult)])
    all_rows = find_outliers(s)
    assert [r["code"] for r in all_rows] == ["startups-tech-hit", "engineering-hit"]
    assert _codes(find_outliers(s, niche="engineering")) == {"engineering-hit"}
    assert len(find_outliers(s, limit=1)) == 1
    assert _codes(find_outliers(s, min_multiple=30)) == {"startups-tech-hit"}


def test_null_followers_and_empty_db():
    s = make_session()
    assert find_outliers(s) == []
    b = Builder(s)
    c = b.creator("ghost", None)
    b.reel(c, "N1", [(T0, 500_000)])
    rows = find_outliers(s)
    assert rows == []  # unknown followers -> not small; single reel -> 1x
