from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query

from app.analytics.formats import format_market, format_timeseries
from app.api.deps import NicheQuery, SessionDep, niche_value
from app.db.models import Format
from app.schemas import FormatMarketRow, FormatTimeseriesPoint

router = APIRouter(prefix="/formats", tags=["formats"])


@router.get("", response_model=list[FormatMarketRow])
def formats(
    session: SessionDep,
    niche: NicheQuery = None,
    weeks: Annotated[int, Query(ge=1, le=104)] = 8,
):
    return format_market(session, niche=niche_value(niche), weeks=weeks)


@router.get("/{format_id}/timeseries", response_model=list[FormatTimeseriesPoint])
def timeseries(session: SessionDep, format_id: Annotated[int, Path(ge=1)]):
    if session.get(Format, format_id) is None:
        raise HTTPException(status_code=404, detail=f"Format {format_id} not found")
    return format_timeseries(session, format_id)
