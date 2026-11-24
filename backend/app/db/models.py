"""SQLAlchemy 2.x models for the Format Arbitrage Tracker (see CONTRACT.md)."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    """Naive UTC timestamp (all datetimes in the DB are naive UTC)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class Creator(Base):
    __tablename__ = "creators"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    niche: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    snapshots: Mapped[list["CreatorSnapshot"]] = relationship(back_populates="creator")
    reels: Mapped[list["Reel"]] = relationship(back_populates="creator")


class ScrapeRun(Base):
    __tablename__ = "scrape_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    niche: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    source: Mapped[str] = mapped_column(String(1024), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    creators_count: Mapped[int] = mapped_column(Integer, default=0)
    reels_count: Mapped[int] = mapped_column(Integer, default=0)


class CreatorSnapshot(Base):
    __tablename__ = "creator_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id"), index=True)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    followers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scrape_run_id: Mapped[int | None] = mapped_column(ForeignKey("scrape_runs.id"), nullable=True)

    creator: Mapped[Creator] = relationship(back_populates="snapshots")


class Reel(Base):
    __tablename__ = "reels"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("creators.id"), index=True)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    # "Paid partnership with ..." reels are brand-boosted, so they're excluded from all analytics.
    is_paid_partnership: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    creator: Mapped[Creator] = relationship(back_populates="reels")
    snapshots: Mapped[list["ReelSnapshot"]] = relationship(back_populates="reel")
    label: Mapped["ReelLabel | None"] = relationship(back_populates="reel", uselist=False)


class ReelSnapshot(Base):
    __tablename__ = "reel_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    reel_id: Mapped[int] = mapped_column(ForeignKey("reels.id"), index=True)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    views: Mapped[int] = mapped_column(Integer)
    likes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comments: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scrape_run_id: Mapped[int | None] = mapped_column(ForeignKey("scrape_runs.id"), nullable=True)

    reel: Mapped[Reel] = relationship(back_populates="snapshots")


class Format(Base):
    __tablename__ = "formats"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    style: Mapped[str | None] = mapped_column(String(128), nullable=True)

    labels: Mapped[list["ReelLabel"]] = relationship(back_populates="format")


class ReelLabel(Base):
    __tablename__ = "reel_labels"

    reel_id: Mapped[int] = mapped_column(ForeignKey("reels.id"), primary_key=True)
    format_id: Mapped[int] = mapped_column(ForeignKey("formats.id"), index=True)
    hook_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    on_screen: Mapped[str | None] = mapped_column(String(255), nullable=True)
    style: Mapped[str | None] = mapped_column(String(128), nullable=True)
    labeled_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    labeled_by: Mapped[str] = mapped_column(String(16), default="agent")  # "agent" | "user"

    reel: Mapped[Reel] = relationship(back_populates="label")
    format: Mapped[Format] = relationship(back_populates="labels")


class HookEmbedding(Base):
    __tablename__ = "hook_embeddings"

    reel_id: Mapped[int] = mapped_column(ForeignKey("reels.id"), primary_key=True)
    model: Mapped[str] = mapped_column(String(128))
    dim: Mapped[int] = mapped_column(Integer)
    vector: Mapped[bytes] = mapped_column(LargeBinary)  # float32 bytes, L2-normalized
