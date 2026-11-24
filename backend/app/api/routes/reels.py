from typing import Annotated

from fastapi import APIRouter, HTTPException, Path
from sqlalchemy import select

from app.api.deps import SessionDep, reel_url
from app.db.models import Creator, CreatorSnapshot, Format, Reel, ReelLabel, ReelSnapshot
from app.schemas import CreatorBrief, LabelOut, ReelDetail, SnapshotOut

router = APIRouter(prefix="/reels", tags=["reels"])


@router.get("/{code}", response_model=ReelDetail)
def reel(session: SessionDep, code: Annotated[str, Path(min_length=1, max_length=64)]) -> ReelDetail:
    r = session.scalar(select(Reel).where(Reel.code == code))
    if r is None:
        raise HTTPException(status_code=404, detail=f"Reel {code!r} not found")

    snaps = list(
        session.scalars(
            select(ReelSnapshot)
            .where(ReelSnapshot.reel_id == r.id)
            .order_by(ReelSnapshot.scraped_at, ReelSnapshot.id)
        )
    )

    creator_out = None
    c = session.get(Creator, r.creator_id)
    if c is not None:
        followers = session.scalar(
            select(CreatorSnapshot.followers)
            .where(CreatorSnapshot.creator_id == c.id)
            .order_by(CreatorSnapshot.scraped_at.desc(), CreatorSnapshot.id.desc())
            .limit(1)
        )
        creator_out = CreatorBrief(username=c.username, niche=c.niche, followers=followers)

    label_out = None
    lbl = session.get(ReelLabel, r.id)
    if lbl is not None:
        fmt = session.get(Format, lbl.format_id) if lbl.format_id is not None else None
        label_out = LabelOut(
            format_id=lbl.format_id,
            format=fmt.name if fmt else None,
            hook_text=lbl.hook_text,
            on_screen=lbl.on_screen,
            style=lbl.style,
            labeled_at=lbl.labeled_at,
            labeled_by=lbl.labeled_by,
        )

    return ReelDetail(
        code=r.code,
        url=reel_url(r.code),
        caption=r.caption,
        duration_s=r.duration_s,
        posted_at=r.posted_at,
        first_seen_at=r.first_seen_at,
        views=snaps[-1].views if snaps else None,
        creator=creator_out,
        label=label_out,
        snapshots=[SnapshotOut.model_validate(s) for s in snaps],
    )
