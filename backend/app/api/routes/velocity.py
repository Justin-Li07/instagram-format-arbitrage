from fastapi import APIRouter

from app.analytics.velocity import bucket_summary, velocity_vs_followers
from app.api.deps import NicheQuery, SessionDep, niche_value
from app.schemas import BucketSummary, VelocityPoint

router = APIRouter(prefix="/velocity", tags=["velocity"])


@router.get("", response_model=list[VelocityPoint])
def velocity(session: SessionDep, niche: NicheQuery = None):
    return velocity_vs_followers(session, niche=niche_value(niche))


@router.get("/buckets", response_model=list[BucketSummary])
def buckets(session: SessionDep, niche: NicheQuery = None):
    return bucket_summary(session, niche=niche_value(niche))
