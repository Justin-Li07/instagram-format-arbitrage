from typing import Annotated

from fastapi import APIRouter, HTTPException, Path
from sqlalchemy import select

from app.analytics.creators import creator_summary, list_creators
from app.api.deps import NicheQuery, SessionDep, niche_value
from app.db.models import Creator
from app.schemas import CreatorDetail, CreatorRow

router = APIRouter(prefix="/creators", tags=["creators"])


@router.get("", response_model=list[CreatorRow])
def creators(session: SessionDep, niche: NicheQuery = None):
    return list_creators(session, niche=niche_value(niche))


@router.get("/{username}", response_model=CreatorDetail)
def creator(session: SessionDep, username: Annotated[str, Path(min_length=1, max_length=64)]):
    if session.scalar(select(Creator.id).where(Creator.username == username)) is None:
        raise HTTPException(status_code=404, detail=f"Creator {username!r} not found")
    return creator_summary(session, username)
