from fastapi import APIRouter

from app.config import APP_VERSION
from app.schemas import Health

router = APIRouter(tags=["meta"])


@router.get("/health", response_model=Health)
def health() -> Health:
    return Health(version=APP_VERSION)
