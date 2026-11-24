from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import NicheQuery, SessionDep
from app.db.models import ScrapeRun
from app.schemas import RunOut

router = APIRouter(tags=["runs"])


@router.get("/runs", response_model=list[RunOut])
def list_runs(
    session: SessionDep,
    niche: NicheQuery = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> list[ScrapeRun]:
    stmt = select(ScrapeRun).order_by(ScrapeRun.started_at.desc(), ScrapeRun.id.desc()).limit(limit)
    if niche is not None:
        stmt = stmt.where(ScrapeRun.niche == niche.value)
    return list(session.scalars(stmt))
