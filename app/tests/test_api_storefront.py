import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.api.storefront import router as storefront_router


@pytest.fixture()
def client():
    app_ = FastAPI()
    app_.include_router(storefront_router)
    return TestClient(app_)


def test_storefront_info_rewrites_host(client):
    resp = client.get("/api/storefront")
    assert resp.status_code == 200
    assert resp.json()["url"] == "http://localhost:8090"


def test_storefront_preview_maps_stock_to_badge(client):
    fake_products = [
        {"id": i, "title": f"Product {i}", "description": "", "price": 9.99, "stock": 1 if i % 2 else 0, "image_url": ""}
        for i in range(1, 26)
    ]
    mock_resp = MagicMock()
    mock_resp.json.return_value = fake_products
    mock_resp.raise_for_status.return_value = None

    with patch("app.api.storefront.httpx.get", return_value=mock_resp):
        resp = client.get("/api/storefront/preview")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_count"] == 25
    assert len(body["products"]) == 6
    assert body["products"][0]["stock_badge"] in ("In stock", "Out of stock")


def test_storefront_preview_handles_mockshop_down(client):
    with patch("app.api.storefront.httpx.get", side_effect=Exception("connection refused")):
        resp = client.get("/api/storefront/preview")
    assert resp.status_code == 200
    assert resp.json() == {"products": [], "total_count": 0}
