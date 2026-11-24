"""404s and query-parameter validation (empty temp DB)."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.main as main_mod
from app.db.models import Base
from app.db.session import get_session


@pytest.fixture(scope="module")
def client():
    tmp = Path(tempfile.mkdtemp(prefix="fa_api_val_"))
    engine = create_engine(f"sqlite:///{(tmp / 'v.db').as_posix()}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def _override():
        s = TestSession()
        try:
            yield s
        finally:
            s.close()

    main_mod.app.dependency_overrides[get_session] = _override
    try:
        yield TestClient(main_mod.app)  # no lifespan: don't touch the real DB
    finally:
        main_mod.app.dependency_overrides.clear()
        engine.dispose()


@pytest.mark.parametrize("path", ["/api/reels/NOPE123", "/api/creators/nobody.here", "/api/formats/999/timeseries"])
def test_404s(client, path):
    assert client.get(path).status_code == 404


def test_similar_unknown_code_404(client):
    assert client.get("/api/hooks/similar", params={"code": "NOPE123"}).status_code == 404


def test_similar_requires_text_or_code(client):
    assert client.get("/api/hooks/similar").status_code == 422


@pytest.mark.parametrize(
    "params",
    [
        {"min_multiple": 0},
        {"min_multiple": -1},
        {"limit": 0},
        {"limit": 1001},
        {"niche": "cooking"},
    ],
)
def test_outlier_param_validation(client, params):
    assert client.get("/api/outliers", params=params).status_code == 422


@pytest.mark.parametrize("path", ["/api/formats", "/api/velocity", "/api/velocity/buckets", "/api/hooks", "/api/creators"])
def test_bad_niche_rejected(client, path):
    assert client.get(path, params={"niche": "cooking"}).status_code == 422


def test_ingest_bad_niche(client):
    r = client.post("/api/ingest/scan", json={"niche": "cooking", "records": [{"u": "a", "f": None, "r": []}]})
    assert r.status_code == 422


def test_empty_db_ok(client):
    assert client.get("/api/outliers", params={"limit": 1000, "min_multiple": 0.5}).json() == []
    assert len(client.get("/api/niches").json()) == 4
