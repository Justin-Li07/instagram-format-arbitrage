"""Shared in-memory DB + builder helpers for analytics tests (no tests of its own besides a smoke check)."""
from __future__ import annotations

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db.models import (  # noqa: E402
    Base,
    Creator,
    CreatorSnapshot,
    Format,
    Reel,
    ReelLabel,
    ReelSnapshot,
)

T0 = datetime(2026, 11, 1, 12, 0, 0)


def make_session() -> Session:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return Session(engine)


class Builder:
    def __init__(self, session: Session):
        self.s = session
        self._formats: dict[str, Format] = {}

    def creator(self, username, followers, niche="engineering", at=T0):
        c = Creator(username=username, niche=niche, first_seen_at=at, last_seen_at=at)
        self.s.add(c)
        self.s.flush()
        self.s.add(CreatorSnapshot(creator_id=c.id, scraped_at=at, followers=followers))
        self.s.flush()
        return c

    def fmt(self, name):
        if name not in self._formats:
            f = Format(name=name, description=f"{name} desc")
            self.s.add(f)
            self.s.flush()
            self._formats[name] = f
        return self._formats[name]

    def reel(self, creator, code, snaps, first_seen=None, posted_at=None, fmt=None, hook=None):
        """snaps: list of (datetime, views)."""
        first_seen = first_seen or snaps[0][0]
        r = Reel(code=code, creator_id=creator.id, first_seen_at=first_seen, posted_at=posted_at)
        self.s.add(r)
        self.s.flush()
        for ts, v in snaps:
            self.s.add(ReelSnapshot(reel_id=r.id, scraped_at=ts, views=v))
        if fmt:
            f = self.fmt(fmt)
            self.s.add(ReelLabel(reel_id=r.id, format_id=f.id, hook_text=hook, labeled_at=T0))
        self.s.flush()
        return r


def test_fixture_smoke():
    s = make_session()
    b = Builder(s)
    c = b.creator("a", 100)
    b.reel(c, "X1", [(T0, 5)], fmt="F", hook="h")
    assert s.query(Reel).count() == 1
