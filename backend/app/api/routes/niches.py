from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import SessionDep
from app.config import NICHES
from app.db.models import Creator, Reel, ScrapeRun
from app.schemas import NicheSummary

router = APIRouter(tags=["meta"])


@router.get("/niches", response_model=list[NicheSummary])
def list_niches(session: SessionDep) -> list[NicheSummary]:
    creators = dict(
        session.execute(select(Creator.niche, func.count(Creator.id)).group_by(Creator.niche)).all()
    )
    reels = dict(
        session.execute(
            select(Creator.niche, func.count(Reel.id))
            .join(Reel, Reel.creator_id == Creator.id)
            .group_by(Creator.niche)
        ).all()
    )
    last = dict(
        session.execute(
            select(ScrapeRun.niche, func.max(ScrapeRun.started_at)).group_by(ScrapeRun.niche)
        ).all()
    )
    return [
        NicheSummary(
            niche=n,
            creators=creators.get(n, 0),
            reels=reels.get(n, 0),
            last_scraped_at=last.get(n),
        )
        for n in NICHES
    ]
