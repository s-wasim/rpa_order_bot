import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

import app.db as db
from app.db import Base


@pytest.fixture()
def client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db.engine = engine
    db.SessionLocal = db.sessionmaker(bind=engine)
    monkeypatch.setattr(db, "init_db", lambda *a, **kw: None)

    from app.server import app as fastapi_app
    return TestClient(fastapi_app)


def test_all_routers_mounted(client):
    assert client.get("/api/health").status_code in (200, 500)
    assert client.get("/api/inventory").status_code == 200
    assert client.get("/api/orders").status_code == 200
    assert client.get("/api/runs").status_code == 200


def test_frontend_index_served(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "RPA Order Bot" in resp.text or "<html" in resp.text.lower()
