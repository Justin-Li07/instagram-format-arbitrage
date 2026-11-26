"""Pydantic request/response models for the HTTP API.

Analytics functions return plain dicts; the models below declare the contract
fields and allow extras so richer analytics output passes through untouched.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Niche(str, Enum):
    engineering = "engineering"
    university_life = "university-life"
    startups_tech = "startups-tech"
    growth_viral = "growth-viral"


class _Open(BaseModel):
    """Response model that tolerates extra keys from analytics dicts."""

    model_config = ConfigDict(extra="allow", from_attributes=True)


# ---------- misc ----------
class Health(BaseModel):
    status: Literal["ok"] = "ok"
    version: str


class NicheSummary(BaseModel):
    niche: str
    creators: int
    reels: int
    last_scraped_at: datetime | None = None


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    niche: str
    source: str
    started_at: datetime | None = None
    creators_count: int
    reels_count: int


# ---------- ingest ----------
class ScanIngest(BaseModel):
    niche: Niche
    scraped_at: datetime | None = None
    records: list[dict[str, Any]] = Field(..., min_length=1)


class LabelsIngest(BaseModel):
    records: list[dict[str, Any]] = Field(..., min_length=1)


class LabelsResult(BaseModel):
    imported: int


# ---------- analytics ----------
class Outlier(_Open):
    code: str
    url: str | None = None
    creator: str | None = None
    niche: str | None = None
    followers: int | None = None
    views: int | None = None
    creator_median: float | None = None
    multiple: float | None = None
    is_small_creator: bool | None = None
    views_per_follower: float | None = None
    views_tier: str | None = None
    follower_tier: str | None = None
    sweet_spot: bool | None = None
    format: str | None = None
    hook: str | None = None


class FormatMarketRow(_Open):
    format_id: int | None = None
    format: str | None = None
    price: float | None = None
    supply: float | None = None
    n_reels: int | None = None
    n_creators: int | None = None
    small_creator_share: float | None = None
    score: float | None = None
    status: str | None = None


class FormatTimeseriesPoint(_Open):
    week: Any
    median_views: float | None = None
    new_posts: int | None = None


class VelocityPoint(_Open):
    followers: int | None = None
    views: int | None = None
    multiple: float | None = None
    velocity: float | None = None
    code: str | None = None
    creator: str | None = None
    bucket: str | None = None


class BucketSummary(_Open):
    bucket: str | None = None
    median_views: float | None = None
    outlier_rate: float | None = None
    top_format: str | None = None


class HookRow(_Open):
    code: str | None = None
    url: str | None = None
    creator: str | None = None
    hook: str | None = None
    format: str | None = None
    views: int | None = None
    multiple: float | None = None


class SimilarHook(BaseModel):
    code: str
    url: str
    creator: str | None = None
    hook: str | None = None
    format: str | None = None
    views: int | None = None
    score: float


class CreatorRow(_Open):
    username: str | None = None
    niche: str | None = None
    followers: int | None = None
    reel_count: int | None = None
    median_views: float | None = None


class CreatorDetail(_Open):
    username: str | None = None
    niche: str | None = None
    followers: int | None = None
    follower_history: list[dict[str, Any]] = []
    reel_count: int | None = None
    median_views: float | None = None
    reels: list[dict[str, Any]] = []
    outlier_reels: list[dict[str, Any]] = []


# ---------- reel detail ----------
class SnapshotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    scraped_at: datetime
    views: int
    likes: int | None = None
    comments: int | None = None
    scrape_run_id: int | None = None


class LabelOut(BaseModel):
    format_id: int | None = None
    format: str | None = None
    hook_text: str | None = None
    on_screen: str | None = None
    style: str | None = None
    labeled_at: datetime | None = None
    labeled_by: str | None = None


class CreatorBrief(BaseModel):
    username: str
    niche: str | None = None
    followers: int | None = None


class ReelDetail(BaseModel):
    code: str
    url: str
    caption: str | None = None
    duration_s: float | None = None
    posted_at: datetime | None = None
    first_seen_at: datetime | None = None
    views: int | None = None
    creator: CreatorBrief | None = None
    label: LabelOut | None = None
    snapshots: list[SnapshotOut]
