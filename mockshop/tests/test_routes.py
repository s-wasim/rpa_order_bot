import os
import pytest
from httpx import ASGITransport, AsyncClient

os.environ["MOCKSHOP_DB"] = "/tmp/test_mockshop.db"

from main import app
from db import init_db


@pytest.fixture(autouse=True)
def setup_db():
    if os.path.exists("/tmp/test_mockshop.db"):
        os.remove("/tmp/test_mockshop.db")
    init_db()


@pytest.mark.asyncio
async def test_home_status():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/")
    assert r.status_code == 200
    assert "DemoMart" in r.text


@pytest.mark.asyncio
async def test_search_hit():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/search?q=thermal")
    assert r.status_code == 200
    assert "ArcticBond" in r.text or "TX-4" in r.text


@pytest.mark.asyncio
async def test_search_miss():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/search?q=xyznonexistent")
    assert r.status_code == 200
    assert "No products found" in r.text


@pytest.mark.asyncio
async def test_product_detail():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/product/1")
    assert r.status_code == 200
    assert "ArcticBond" in r.text


@pytest.mark.asyncio
async def test_add_to_cart():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/cart/add", data={"product_id": 1, "title": "Test", "price": 9.99, "qty": 2})
    assert r.status_code == 303
    assert r.headers["location"] == "/cart"


@pytest.mark.asyncio
async def test_cart_page():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/cart/add", data={"product_id": 1, "title": "Test Product", "price": 9.99, "qty": 1})
        r = await client.get("/cart")
    assert r.status_code == 200
    assert "Test Product" in r.text


@pytest.mark.asyncio
async def test_checkout_get():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/cart/add", data={"product_id": 1, "title": "Test", "price": 9.99, "qty": 1})
        r = await client.get("/checkout")
    assert r.status_code == 200
    assert "checkout" in r.text.lower()


@pytest.mark.asyncio
async def test_checkout_post():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/cart/add", data={"product_id": 1, "title": "Test Item", "price": 9.99, "qty": 2})
        r = await client.post("/checkout", data={
            "name": "John", "email": "j@t.com", "phone": "555", "address": "123 St"
        }, follow_redirects=True)
    assert r.status_code == 200
    import re
    assert re.search(r"DM-\d{5}", r.text)


@pytest.mark.asyncio
async def test_orders_page():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post("/cart/add", data={"product_id": 1, "title": "Test", "price": 9.99, "qty": 1})
        await client.post("/checkout", data={
            "name": "John", "email": "j@t.com", "phone": "555", "address": "123 St"
        })
        r = await client.get("/orders")
    assert r.status_code == 200
    assert "DM-" in r.text


@pytest.mark.asyncio
async def test_data_testid_attributes():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/")
    assert 'data-testid="search-input"' in r.text
    assert 'data-testid="search-submit"' in r.text
