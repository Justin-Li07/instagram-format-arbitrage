from datetime import timedelta

from test_analytics_fixtures import T0, Builder, make_session

from app.analytics.creators import creator_summary, list_creators
from app.analytics.hooks import top_hooks
from app.db.models import CreatorSnapshot


def _world():
    s = make_session()
    b = Builder(s)
    mid = b.creator("mid", 200_000)
    for i in range(4):
        b.reel(mid, f"M{i}", [(T0, 1_000)], fmt="Vlog", hook=f"boring {i}")
    b.reel(mid, "MHIT", [(T0, 30_000)], fmt="Listicle", hook="5 tools nobody uses")
    tiny = b.creator("tiny", 7_482)
    b.reel(tiny, "THIT", [(T0, 454_000)], fmt="Talking head", hook="I got rejected 40 times")
    b.reel(tiny, "TNOHOOK", [(T0, 300_000)], fmt="Talking head")
    # follower history for tiny
    s.add(CreatorSnapshot(creator_id=tiny.id, scraped_at=T0 + timedelta(days=7), followers=9_000))
    s.flush()
    return s


def test_top_hooks_only_outliers_with_hooks():
    s = _world()
    hooks = top_hooks(s)
    assert [h["code"] for h in hooks] == ["MHIT", "THIT"]  # 30x first, then small creator
    assert hooks[0]["hook"] == "5 tools nobody uses"
    assert hooks[0]["format"] == "Listicle"
    assert hooks[0]["multiple"] == 30.0
    assert hooks[1]["views"] == 454_000
    assert len(top_hooks(s, limit=1)) == 1
    assert top_hooks(s, niche="startups-tech") == []


def test_creator_summary():
    s = _world()
    d = creator_summary(s, "tiny")
    assert d["followers"] == 9_000  # latest snapshot
    assert [h["followers"] for h in d["follower_history"]] == [7_482, 9_000]
    assert d["reel_count"] == 2
    assert d["median_views"] == 377_000
    assert {r["code"] for r in d["outlier_reels"]} == {"THIT", "TNOHOOK"}
    assert d["reels"][0]["code"] == "THIT"
    assert creator_summary(s, "nobody") is None


def test_list_creators():
    s = _world()
    rows = list_creators(s)
    by = {r["username"]: r for r in rows}
    assert by["mid"]["reel_count"] == 5
    assert by["mid"]["median_views"] == 1_000
    assert by["mid"]["outlier_count"] == 1
    assert by["tiny"]["outlier_count"] == 2
    assert rows[0]["username"] == "tiny"
    assert list_creators(s, niche="growth-viral") == []
