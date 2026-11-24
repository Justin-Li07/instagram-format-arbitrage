from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.analytics.hooks import top_hooks
from app.api.deps import NicheQuery, SessionDep, niche_value, reel_url
from app.db.models import Creator, Format, Reel, ReelSnapshot
from app.embeddings.embedder import similar_hooks
from app.schemas import HookRow, SimilarHook

router = APIRouter(prefix="/hooks", tags=["hooks"])


@router.get("", response_model=list[HookRow])
def hooks(
    session: SessionDep,
    niche: NicheQuery = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 50,
):
    return top_hooks(session, niche=niche_value(niche), limit=limit)


@router.get("/similar", response_model=list[SimilarHook])
def similar(
    session: SessionDep,
    text: Annotated[str | None, Query(min_length=1, max_length=500)] = None,
    code: Annotated[str | None, Query(min_length=1, max_length=64)] = None,
    k: Annotated[int, Query(ge=1, le=100)] = 10,
) -> list[SimilarHook]:
    if not text and not code:
        raise HTTPException(status_code=422, detail="Provide either `text` or `code`")
    if code and session.scalar(select(Reel.id).where(Reel.code == code)) is None:
        raise HTTPException(status_code=404, detail=f"Reel {code!r} not found")

    results = similar_hooks(session, text=text, reel_code=None if text else code, k=k)

    out: list[SimilarHook] = []
    for reel, label, score in results:
        creator = session.get(Creator, reel.creator_id)
        fmt = session.get(Format, label.format_id) if label.format_id is not None else None
        views = session.scalar(
            select(ReelSnapshot.views)
            .where(ReelSnapshot.reel_id == reel.id)
            .order_by(ReelSnapshot.scraped_at.desc(), ReelSnapshot.id.desc())
            .limit(1)
        )
        out.append(
            SimilarHook(
                code=reel.code,
                url=reel_url(reel.code),
                creator=creator.username if creator else None,
                hook=label.hook_text,
                format=fmt.name if fmt else None,
                views=views,
                score=float(score),
            )
        )
    return out
