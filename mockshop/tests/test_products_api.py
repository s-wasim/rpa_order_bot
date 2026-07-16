import os
import pytest
from httpx import ASGITransport, AsyncClient

os.environ["MOCKSHOP_DB"] = "/tmp/test_mockshop_products.db"

from main import app
from db import init_db


@pytest.fixture(autouse=True)
def setup_db():
    if os.path.exists("/tmp/test_mockshop_products.db"):
        os.remove("/tmp/test_mockshop_products.db")
    init_db()


@pytest.mark.asyncio
async def test_products_api_returns_full_catalog():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/products")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 25
    assert {"id", "title", "description", "price", "stock", "image_url"} <= set(body[0].keys())
    assert any(p["title"].startswith("ArcticBond") for p in body)
