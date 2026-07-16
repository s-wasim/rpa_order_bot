import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

import app.db as db
from app.db import Base, Inventory, get_session
from app.api.inventory import router as inventory_router


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db.engine = engine
    db.SessionLocal = db.sessionmaker(bind=engine)

    with get_session() as session:
        session.add(Inventory(sku="AAA-1", name="Low Item", qty=1, reorder_threshold=5, reorder_qty=10, on_order=0))
        session.add(Inventory(sku="ZZZ-9", name="Stocked Item", qty=20, reorder_threshold=5, reorder_qty=10, on_order=0))

    app_ = FastAPI()
    app_.include_router(inventory_router)
    return TestClient(app_)


def test_get_inventory_sorted_and_low_flag(client):
    resp = client.get("/api/inventory")
    assert resp.status_code == 200
    body = resp.json()
    assert [i["sku"] for i in body] == ["AAA-1", "ZZZ-9"]
    assert body[0]["low"] is True
    assert body[1]["low"] is False


def test_save_thresholds(client):
    resp = client.post("/api/inventory/thresholds", json=[{"sku": "AAA-1", "reorder_threshold": 8, "reorder_qty": 15}])
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    resp2 = client.get("/api/inventory")
    updated = next(i for i in resp2.json() if i["sku"] == "AAA-1")
    assert updated["reorder_threshold"] == 8
    assert updated["reorder_qty"] == 15
