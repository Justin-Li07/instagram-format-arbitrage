from fastapi import APIRouter, HTTPException, status

from app.api.deps import SessionDep, to_naive_utc, utcnow
from app.ingest.importer import import_labels, import_scan_records
from app.schemas import LabelsIngest, LabelsResult, RunOut, ScanIngest

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/scan", response_model=RunOut, status_code=status.HTTP_201_CREATED)
def ingest_scan(body: ScanIngest, session: SessionDep):
    scraped_at = to_naive_utc(body.scraped_at) or utcnow()
    try:
        run = import_scan_records(
            session, body.records, niche=body.niche.value, scraped_at=scraped_at, source="api"
        )
        session.commit()
    except (KeyError, ValueError, TypeError) as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=f"Bad scan records: {exc}") from exc
    session.refresh(run)
    return run


@router.post("/labels", response_model=LabelsResult)
def ingest_labels(body: LabelsIngest, session: SessionDep) -> LabelsResult:
    try:
        n = import_labels(session, body.records)
        session.commit()
    except (KeyError, ValueError, TypeError) as exc:
        session.rollback()
        raise HTTPException(status_code=422, detail=f"Bad label records: {exc}") from exc
    return LabelsResult(imported=int(n))
