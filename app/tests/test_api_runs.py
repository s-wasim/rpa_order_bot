import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from unittest.mock import patch

import app.db as db
from app.db import Base, Run, RunStep, Inventory, get_session
from app.api.runs import router as runs_router


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db.engine = engine
    db.SessionLocal = db.sessionmaker(bind=engine)

    with get_session() as session:
        session.add(Inventory(sku="LOW-1", name="Low Item", qty=1, reorder_threshold=5, reorder_qty=10, on_order=0))

    app_ = FastAPI()
    app_.include_router(runs_router)
    return TestClient(app_)


def test_start_run_launches_agent_and_returns_immediately(client):
    with patch("app.api.runs.run_agent") as mock_run_agent:
        mock_run_agent.side_effect = lambda run_id: time.sleep(0.2)
        resp = client.post("/api/runs")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert isinstance(body["run_id"], int)

    with get_session() as session:
        run = session.query(Run).filter_by(id=body["run_id"]).first()
        assert run.status == "running"


def test_start_run_rejected_when_nothing_low(client):
    with get_session() as session:
        session.query(Inventory).filter_by(sku="LOW-1").update({"qty": 99})

    resp = client.post("/api/runs")
    body = resp.json()
    assert body["ok"] is False
    assert "adequately stocked" in body["reason"]


def test_start_run_rejected_when_already_running(client):
    with get_session() as session:
        session.add(Run(status="running"))

    resp = client.post("/api/runs")
    body = resp.json()
    assert body["ok"] is False
    assert "already in progress" in body["reason"]


def test_failed_agent_marks_run_failed_not_stuck_running(client):
    with patch("app.api.runs.run_agent", side_effect=RuntimeError("playwright boom")):
        resp = client.post("/api/runs")
    run_id = resp.json()["run_id"]

    deadline = time.time() + 2
    with get_session() as session:
        run = session.query(Run).filter_by(id=run_id).first()
        while run.status == "running" and time.time() < deadline:
            session.expire(run)
            time.sleep(0.05)
            run = session.query(Run).filter_by(id=run_id).first()
        assert run.status == "failed"
        assert run.summary_json["error"] == "playwright boom"


def test_list_runs_and_get_run_detail(client):
    with get_session() as session:
        run = Run(status="succeeded", plan_json=[{"sku": "LOW-1", "name": "Low Item", "search_terms": "low item", "quantity": 10, "notes": ""}])
        session.add(run)
        session.flush()
        session.add(RunStep(run_id=run.id, seq=1, label="Search", detail="Searching", status="succeeded", screenshot_path="/data/screenshots/1/001_search.png", reasoning=None))
        run.summary_json = {"ordered": 1, "skipped": 0, "failed": 0, "total": 9.99, "order_number": "DM-1", "item_results": [{"sku": "LOW-1", "name": "Low Item", "status": "matched", "reasoning": "Good match", "qty": 10}]}
        run_id = run.id

    list_resp = client.get("/api/runs")
    assert list_resp.status_code == 200
    assert list_resp.json()[0]["id"] == run_id

    detail_resp = client.get(f"/api/runs/{run_id}")
    detail = detail_resp.json()
    assert detail["status"] == "succeeded"
    assert detail["plan_json"][0]["sku"] == "LOW-1"
    assert detail["summary_json"]["order_number"] == "DM-1"
    assert detail["steps"][0]["screenshot_path"] == f"{run_id}/001_search.png"


def test_get_run_not_found_returns_null(client):
    resp = client.get("/api/runs/999")
    assert resp.status_code == 200
    assert resp.json() is None


def test_stream_run_emits_status_and_terminates(client):
    with get_session() as session:
        run = Run(status="succeeded", summary_json={"ordered": 0, "skipped": 0, "failed": 0, "total": 0, "order_number": None, "item_results": []})
        session.add(run)
        session.flush()
        run_id = run.id

    with client.stream("GET", f"/api/runs/{run_id}/stream") as resp:
        assert resp.status_code == 200
        chunks = b"".join(resp.iter_bytes())
    assert b"event: status" in chunks
    assert b"succeeded" in chunks
