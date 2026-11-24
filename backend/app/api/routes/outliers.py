from typing import Annotated

from fastapi import APIRouter, Query

from app.analytics.outliers import find_outliers
from app.api.deps import NicheQuery, SessionDep, niche_value
from app.schemas import Outlier

router = APIRouter(tags=["outliers"])


@router.get("/outliers", response_model=list[Outlier])
def outliers(
    session: SessionDep,
    niche: NicheQuery = None,
    min_multiple: Annotated[float, Query(gt=0)] = 10.0,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
):
    return find_outliers(session, niche=niche_value(niche), min_multiple=min_multiple, limit=limit)
