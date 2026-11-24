"""Shared dependencies and helpers for API routes."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.schemas import Niche

SessionDep = Annotated[Session, Depends(get_session)]
NicheQuery = Annotated[Niche | None, Query(description="One of the 4 niches; omit for all")]


def niche_value(niche: Niche | None) -> str | None:
    return niche.value if niche is not None else None


def reel_url(code: str) -> str:
    return f"https://www.instagram.com/reel/{code}/"


def to_naive_utc(dt: datetime | None) -> datetime | None:
    """SQLite stores naive datetimes; normalise aware inputs to naive UTC."""
    if dt is None or dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
