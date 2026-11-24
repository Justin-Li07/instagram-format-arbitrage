"""Engine / session setup. `FA_DB_URL` overrides the default SQLite file."""
from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import Base

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DB_URL = f"sqlite:///{(BACKEND_DIR / 'formatarb.db').as_posix()}"


def make_engine(url: str | None = None) -> Engine:
    url = url or os.environ.get("FA_DB_URL") or DEFAULT_DB_URL
    kwargs = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)


engine: Engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db(bind: Engine | None = None) -> None:
    """Create all tables (no-op for ones that already exist), then add any columns added later."""
    bind = bind or engine
    Base.metadata.create_all(bind)
    _add_missing_columns(bind)


# Columns added after the first release: (table, column, SQL type + default).
_LATE_COLUMNS = [("reels", "is_paid_partnership", "BOOLEAN NOT NULL DEFAULT 0")]


def _add_missing_columns(bind: Engine) -> None:
    """Tiny migration step: create_all() never alters existing tables, so add new columns here."""
    from sqlalchemy import inspect, text

    insp = inspect(bind)
    with bind.begin() as conn:
        for table, column, ddl in _LATE_COLUMNS:
            if table in insp.get_table_names() and column not in {c["name"] for c in insp.get_columns(table)}:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


def get_session() -> Iterator[Session]:
    """FastAPI dependency: yields a Session and closes it afterwards."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
