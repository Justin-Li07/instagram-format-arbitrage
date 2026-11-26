from test_analytics_fixtures import T0, Builder, make_session

from app.analytics.outliers import find_breakouts


def test_breakouts_small_creators_only_and_tiers():
    s = make_session()
    b = Builder(s)
    sweet = b.creator("sweet", 3_000)
    b.reel(sweet, "MIL", [(T0, 1_200_000)])
    b.reel(sweet, "HALF", [(T0, 600_000)])
    b.reel(sweet, "LOW", [(T0, 400_000)])  # under 500K -> not a breakout
    tiny = b.creator("tiny", 800)
    b.reel(tiny, "TINY", [(T0, 700_000)])
    mid = b.creator("mid", 8_000)
    b.reel(mid, "MID", [(T0, 900_000)])
    big = b.creator("big", 50_000)
    b.reel(big, "BIG", [(T0, 5_000_000)])  # big account -> audience explains it
    rows = find_breakouts(s)
    by = {r["code"]: r for r in rows}
    assert set(by) == {"MIL", "HALF", "TINY", "MID"}
    assert by["MIL"]["views_tier"] == "1M+" and by["MIL"]["sweet_spot"] is True
    assert by["HALF"]["views_tier"] == "500K+" and by["HALF"]["follower_tier"] == "1-5K"
    assert by["TINY"]["follower_tier"] == "<1K"
    assert by["MID"]["follower_tier"] == "5-10K"
    assert rows[0]["code"] == "MIL"
