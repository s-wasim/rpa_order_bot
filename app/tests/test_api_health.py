import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from unittest.mock import patch

import app.db as db
from app.db import Base
from app.api.health import router as health_router


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db.engine = engine
    db.SessionLocal = db.sessionmaker(bind=engine)

    app_ = FastAPI()
    app_.include_router(health_router)
    return TestClient(app_)


def test_health_ok(client):
    with patch("app.api.health.httpx.get") as mock_get:
        mock_get.return_value.status_code = 200
        resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["db_ok"] is True
    assert body["demomart_ok"] is True
    assert body["error"] is None


def test_health_demomart_down(client):
    with patch("app.api.health.httpx.get", side_effect=Exception("connection refused")):
        resp = client.get("/api/health")
    body = resp.json()
    assert body["demomart_ok"] is False
    assert body["error"] == "DemoMart storefront is unreachable"
