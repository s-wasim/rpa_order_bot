import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

import app.db as db
from app.db import Base, Run, Order, OrderItem, get_session
from app.api.orders import router as orders_router


@pytest.fixture()
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db.engine = engine
    db.SessionLocal = db.sessionmaker(bind=engine)

    with get_session() as session:
        run = Run(status="succeeded")
        session.add(run)
        session.flush()
        order = Order(run_id=run.id, demomart_order_no="DM-99001", total=19.98)
        session.add(order)
        session.flush()
        session.add(OrderItem(order_id=order.id, sku="SKU-1", product_title="Widget", qty=2, unit_price=9.99))

    app_ = FastAPI()
    app_.include_router(orders_router)
    return TestClient(app_)


def test_list_orders(client):
    resp = client.get("/api/orders")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["demomart_order_no"] == "DM-99001"
    assert body[0]["items"][0]["product_title"] == "Widget"
    assert body[0]["items"][0]["qty"] == 2
