# RPA Order Bot: Streamlit → FastAPI + dc-runtime Frontend — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Streamlit UI in `rpa_order_bot [Published]` with the existing dc-runtime frontend template (`frontend/RPA Order Bot.dc.html`), backed by a real FastAPI service, with no functional regressions and two feature completions (real storefront product preview, real screenshot rendering).

**Architecture:** A single FastAPI app (`app/server.py`) registers per-resource API routers under `app/api/` and mounts `frontend/` as static files on the same origin. `mockshop` (a separate service) gains one new JSON endpoint. `adapter.js` and the `.dc.html` template are updated to call the real endpoints instead of in-memory mocks.

**Tech Stack:** FastAPI, Uvicorn, SQLAlchemy (existing), httpx, pytest + FastAPI TestClient, existing LangGraph/Playwright/Anthropic stack (untouched).

## Global Constraints

- Every new API response shape must match the field names already documented in `frontend/adapter.js`'s mock functions and consumed by `frontend/RPA Order Bot.dc.html` — the frontend template itself does not change except where explicitly noted in Task 10.
- Existing DB models, LangGraph nodes, and Playwright step modules keep their current behavior except the one explicit addition in Task 1 (persisting `reasoning`). Do not refactor unrelated code.
- All new Python files follow the existing project's import style: `from app.db import ...`, `from app.api.schemas import ...` (absolute imports rooted at the `app` package, matching every existing file in `app/`).
- Every task that adds backend behavior includes a test using an in-memory SQLite DB (`sqlite://` with `StaticPool` + `check_same_thread=False`, per `inbound_lead_responder`'s established pattern) and FastAPI's `TestClient`.

---

## Execution Waves (for parallel dispatch)

Tasks within a wave touch disjoint files and have no dependencies on each other — dispatch them to parallel subagents. Do not start a wave until every task in the previous wave is committed.

- **Wave 0 (parallel):** Task 1, Task 2
- **Wave 1 (parallel, depends on Wave 0):** Task 3, Task 4, Task 5, Task 6, Task 7, Task 8, Task 9, Task 10, Task 11, Task 12
- **Wave 2 (sequential, depends on all of Wave 1):** Task 13
- **Wave 3 (sequential, depends on Task 13):** Task 14
- **Wave 4 (sequential, depends on Task 14):** Task 15

---

### Task 1: Persist `reasoning` on RunStep rows

The real `browse_and_match_item` node computes a `reasoning` string (why Claude picked/rejected a candidate) but today only the *skip* case happens to save it (crammed into the `detail` field). The *matched* and *failed* cases never persist it, even though the frontend template renders a dedicated italic "reasoning quote" block for any step (`hasReasoning: !!step.reasoning`) — this is the demo's core pitch ("AI explains why it matched or skipped"). Add a real `reasoning` column and persist it in every case.

**Files:**
- Modify: `app/db.py` (add column to `RunStep`)
- Modify: `app/graph/nodes/browse.py:13-124` (`_save_step` signature + all three call sites)
- Test: `app/tests/test_db.py` (extend), `app/tests/test_browse_node.py` (no signature changes needed — these tests mock `get_session` entirely, so they keep passing unchanged)

**Interfaces:**
- Produces: `RunStep.reasoning: Optional[str]` column; `_save_step(run_id, seq, label, detail, status, screenshot_path=None, reasoning=None)` — the new trailing keyword param later tasks (Task 7) read via `RunStep.reasoning`.

- [ ] **Step 1: Write the failing test for the new column**

Add to `app/tests/test_db.py`:

```python
def test_run_step_reasoning_column(db_session):
    run = Run(status="running")
    db_session.add(run)
    db_session.flush()

    step = RunStep(run_id=run.id, seq=1, label="Cart item", status="succeeded", reasoning="Exact title match.")
    db_session.add(step)
    db_session.commit()

    fetched = db_session.query(RunStep).filter_by(id=step.id).one()
    assert fetched.reasoning == "Exact title match."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "app" && python -m pytest tests/test_db.py::test_run_step_reasoning_column -v`
Expected: FAIL with `TypeError: 'reasoning' is an invalid keyword argument for RunStep`

- [ ] **Step 3: Add the column**

In `app/db.py`, inside the `RunStep` class (after the existing `status` column, before `created_at`):

```python
    reasoning = Column(Text, nullable=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "app" && python -m pytest tests/test_db.py::test_run_step_reasoning_column -v`
Expected: PASS

- [ ] **Step 5: Update `_save_step` and its call sites in `app/graph/nodes/browse.py`**

Replace the whole file's content with:

```python
from app.browser import take_screenshot
from app.db import get_session
from app.db import RunStep
from app.llm import get_llm
from app.graph.registry import get_registry
from app.graph.state import OrderState, ItemResult
from app.steps import StepError
from app.steps.search import search_product
from app.steps.match import match_product
from app.steps.cart import add_to_cart


def _save_step(run_id: int, seq: int, label: str, detail: str, status: str, screenshot_path: str = None, reasoning: str = None):
    with get_session() as session:
        step = RunStep(
            run_id=run_id,
            seq=seq,
            label=label,
            detail=detail,
            status=status,
            screenshot_path=screenshot_path,
            reasoning=reasoning,
        )
        session.add(step)


def browse_and_match_item(state: OrderState) -> OrderState:
    llm = get_llm()
    page = get_registry().get_page()
    plan = state["plan"]
    idx = state["current_index"]
    item = plan[idx]
    screenshots = list(state.get("screenshots", []))

    seq = idx * 10 + 1
    _save_step(state["run_id"], seq, f"Search for {item['name']}", f"Searching for: {item['search_terms']}", "running")

    candidates = search_product(page, item["search_terms"])
    ss = take_screenshot(page, state["run_id"], seq, f"search_{item['sku']}")
    screenshots.append(ss)

    inv_item = next((x for x in state["low_stock"] if x["sku"] == item["sku"]), {})
    match_result = match_product(llm, inv_item, candidates)

    choice = match_result["choice_index"]
    reasoning = match_result["reasoning"]

    if choice is None or choice >= len(candidates):
        result: ItemResult = {
            "sku": item["sku"],
            "name": item["name"],
            "status": "skipped",
            "reasoning": reasoning,
            "product_title": None,
            "unit_price": None,
            "quantity": item["quantity"],
        }
        _save_step(state["run_id"], seq + 1, f"Skip {item['name']}", reasoning, "skipped", ss, reasoning=reasoning)
        return {
            **state,
            "item_results": [*state.get("item_results", []), result],
            "current_index": idx + 1,
            "screenshots": screenshots,
        }

    candidate = candidates[choice]

    try:
        cart_result = add_to_cart(page, candidate["url"], item["quantity"])
        ss2 = take_screenshot(page, state["run_id"], seq, f"cart_{item['sku']}")
        screenshots.append(ss2)

        result = {
            "sku": item["sku"],
            "name": item["name"],
            "status": "matched",
            "reasoning": reasoning,
            "product_title": candidate["title"],
            "unit_price": candidate["price"],
            "quantity": item["quantity"],
        }
        _save_step(
            state["run_id"], seq + 1,
            f"Cart {item['name']}",
            f"Added {item['quantity']}× {candidate['title']} to cart",
            "succeeded", ss2, reasoning=reasoning,
        )
    except StepError as e:
        try:
            cart_result = add_to_cart(page, candidate["url"], item["quantity"])
            ss2 = take_screenshot(page, state["run_id"], seq, f"cart_retry_{item['sku']}")
            screenshots.append(ss2)
            result = {
                "sku": item["sku"],
                "name": item["name"],
                "status": "matched",
                "reasoning": f"Retry succeeded: {reasoning}",
                "product_title": candidate["title"],
                "unit_price": candidate["price"],
                "quantity": item["quantity"],
            }
            _save_step(
                state["run_id"], seq + 1,
                f"Cart {item['name']}",
                f"Added {item['quantity']}× {candidate['title']} to cart (after retry)",
                "succeeded", ss2, reasoning=f"Retry succeeded: {reasoning}",
            )
        except StepError as e2:
            result = {
                "sku": item["sku"],
                "name": item["name"],
                "status": "failed",
                "reasoning": f"Cart add failed: {e2}",
                "product_title": candidate["title"],
                "unit_price": candidate["price"],
                "quantity": item["quantity"],
            }
            _save_step(state["run_id"], seq + 1, f"Cart {item['name']}", f"Failed: {e2}", "failed", ss, reasoning=f"Cart add failed: {e2}")

    return {
        **state,
        "item_results": [*state.get("item_results", []), result],
        "current_index": idx + 1,
        "screenshots": screenshots,
    }
```

- [ ] **Step 6: Run the full existing graph/node test suite to confirm no regressions**

Run: `cd "app" && python -m pytest tests/test_browse_node.py tests/test_db.py -v`
Expected: all PASS (existing tests mock `get_session`, so the new keyword arg is invisible to them)

- [ ] **Step 7: Commit**

```bash
git add app/db.py app/graph/nodes/browse.py app/tests/test_db.py
git commit -m "feat: persist match/skip reasoning on RunStep rows"
```

---

### Task 2: API schemas (`app/api/schemas.py`)

**Files:**
- Create: `app/api/__init__.py` (empty)
- Create: `app/api/schemas.py`
- Test: none (pure data classes; exercised by every router's tests in Wave 1)

**Interfaces:**
- Produces: every Pydantic model imported by Tasks 3–9 — `InventoryItemOut`, `ThresholdEdit`, `RunListItem`, `PlanItemOut`, `RunStepOut`, `ItemResultOut`, `RunSummaryOut`, `RunDetailOut`, `StartRunResponse`, `OrderItemOut`, `OrderOut`, `HealthOut`, `StorefrontInfoOut`, `StorefrontProductOut`, `StorefrontPreviewOut`.

- [ ] **Step 1: Create the package init**

```bash
touch "app/api/__init__.py"
```

- [ ] **Step 2: Write `app/api/schemas.py`**

```python
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class InventoryItemOut(BaseModel):
    sku: str
    name: str
    qty: int
    reorder_threshold: int
    reorder_qty: int
    on_order: int
    low: bool


class ThresholdEdit(BaseModel):
    sku: str
    reorder_threshold: int
    reorder_qty: int


class RunListItem(BaseModel):
    id: int
    created_at: datetime
    status: str


class PlanItemOut(BaseModel):
    sku: str
    name: str
    search_terms: str
    quantity: int
    notes: str


class RunStepOut(BaseModel):
    id: int
    seq: int
    label: str
    detail: Optional[str] = None
    status: str
    screenshot_path: Optional[str] = None
    reasoning: Optional[str] = None


class ItemResultOut(BaseModel):
    sku: str
    name: str
    status: str
    reasoning: Optional[str] = None
    qty: int


class RunSummaryOut(BaseModel):
    ordered: int
    skipped: int
    failed: int
    total: float
    order_number: Optional[str] = None
    item_results: list[ItemResultOut]


class RunDetailOut(BaseModel):
    id: int
    created_at: datetime
    status: str
    plan_json: Optional[list[PlanItemOut]] = None
    summary_json: Optional[RunSummaryOut] = None
    steps: list[RunStepOut]


class StartRunResponse(BaseModel):
    ok: bool
    run_id: Optional[int] = None
    reason: Optional[str] = None


class OrderItemOut(BaseModel):
    sku: Optional[str] = None
    product_title: str
    qty: int
    unit_price: float


class OrderOut(BaseModel):
    demomart_order_no: str
    total: float
    created_at: datetime
    run_id: int
    items: list[OrderItemOut]


class HealthOut(BaseModel):
    db_ok: bool
    demomart_ok: bool
    error: Optional[str] = None


class StorefrontInfoOut(BaseModel):
    url: str


class StorefrontProductOut(BaseModel):
    title: str
    price: float
    stock_badge: str


class StorefrontPreviewOut(BaseModel):
    products: list[StorefrontProductOut]
    total_count: int
```

- [ ] **Step 3: Verify it imports cleanly**

Run: `cd "app/.." && python -c "from app.api.schemas import RunDetailOut, StartRunResponse; print('ok')"`
Expected: prints `ok`

- [ ] **Step 4: Commit**

```bash
git add app/api/__init__.py app/api/schemas.py
git commit -m "feat: add Pydantic API schemas"
```

---

### Task 3: Health router

**Files:**
- Create: `app/api/health.py`
- Test: `app/tests/test_api_health.py`

**Interfaces:**
- Consumes: `HealthOut` from Task 2; `get_session` from `app.db`; `settings.MOCKSHOP_URL` from `app.settings`.
- Produces: `router` (FastAPI `APIRouter`) registered by Task 13 as `GET /api/health`.

- [ ] **Step 1: Write the failing test**

Create `app/tests/test_api_health.py`:

```python
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
```

Note: `db.sessionmaker` must be accessible as an attribute — `app/db.py` already does `from sqlalchemy.orm import ... sessionmaker` at module level, so `db.sessionmaker` resolves fine.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "app/.." && python -m pytest app/tests/test_api_health.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.api.health'`

- [ ] **Step 3: Write `app/api/health.py`**

```python
from sqlalchemy import text
import httpx
from fastapi import APIRouter

from app.api.schemas import HealthOut
from app.db import get_session
from app import settings

router = APIRouter()


@router.get("/api/health", response_model=HealthOut)
def get_health():
    db_ok = True
    try:
        with get_session() as session:
            session.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    demomart_ok = True
    try:
        resp = httpx.get(settings.MOCKSHOP_URL, timeout=3.0)
        demomart_ok = resp.status_code < 500
    except Exception:
        demomart_ok = False

    error = None if demomart_ok else "DemoMart storefront is unreachable"
    return HealthOut(db_ok=db_ok, demomart_ok=demomart_ok, error=error)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "app/.." && python -m pytest app/tests/test_api_health.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add app/api/health.py app/tests/test_api_health.py
git commit -m "feat: add GET /api/health endpoint"
```

---

### Task 4: Inventory router

**Files:**
- Create: `app/api/inventory.py`
- Test: `app/tests/test_api_inventory.py`

**Interfaces:**
- Consumes: `InventoryItemOut`, `ThresholdEdit` from Task 2; `Inventory` model from `app.db`.
- Produces: `router` registered by Task 13 as `GET /api/inventory`, `POST /api/inventory/thresholds`.

- [ ] **Step 1: Write the failing test**

Create `app/tests/test_api_inventory.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "app/.." && python -m pytest app/tests/test_api_inventory.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.api.inventory'`

- [ ] **Step 3: Write `app/api/inventory.py`**

```python
from fastapi import APIRouter

from app.api.schemas import InventoryItemOut, ThresholdEdit
from app.db import get_session, Inventory

router = APIRouter()


def _is_low(item: Inventory) -> bool:
    return (item.qty + item.on_order) < item.reorder_threshold


@router.get("/api/inventory", response_model=list[InventoryItemOut])
def get_inventory():
    with get_session() as session:
        items = session.query(Inventory).order_by(Inventory.sku).all()
        return [
            InventoryItemOut(
                sku=i.sku, name=i.name, qty=i.qty,
                reorder_threshold=i.reorder_threshold, reorder_qty=i.reorder_qty,
                on_order=i.on_order, low=_is_low(i),
            )
            for i in items
        ]


@router.post("/api/inventory/thresholds")
def save_thresholds(edits: list[ThresholdEdit]):
    with get_session() as session:
        for edit in edits:
            inv = session.query(Inventory).filter(Inventory.sku == edit.sku).first()
            if inv:
                inv.reorder_threshold = edit.reorder_threshold
                inv.reorder_qty = edit.reorder_qty
    return {"ok": True}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "app/.." && python -m pytest app/tests/test_api_inventory.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add app/api/inventory.py app/tests/test_api_inventory.py
git commit -m "feat: add inventory API endpoints"
```

---

### Task 5: Orders router

**Files:**
- Create: `app/api/orders.py`
- Test: `app/tests/test_api_orders.py`

**Interfaces:**
- Consumes: `OrderOut`, `OrderItemOut` from Task 2; `Order`, `OrderItem` models from `app.db`.
- Produces: `router` registered by Task 13 as `GET /api/orders`.

- [ ] **Step 1: Write the failing test**

Create `app/tests/test_api_orders.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "app/.." && python -m pytest app/tests/test_api_orders.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.api.orders'`

- [ ] **Step 3: Write `app/api/orders.py`**

```python
from fastapi import APIRouter

from app.api.schemas import OrderOut, OrderItemOut
from app.db import get_session, Order

router = APIRouter()


@router.get("/api/orders", response_model=list[OrderOut])
def list_orders():
    with get_session() as session:
        orders = session.query(Order).order_by(Order.created_at.desc()).all()
        return [
            OrderOut(
                demomart_order_no=o.demomart_order_no, total=o.total,
                created_at=o.created_at, run_id=o.run_id,
                items=[
                    OrderItemOut(sku=i.sku, product_title=i.product_title, qty=i.qty, unit_price=i.unit_price)
                    for i in o.items
                ],
            )
            for o in orders
        ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "app/.." && python -m pytest app/tests/test_api_orders.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/api/orders.py app/tests/test_api_orders.py
git commit -m "feat: add GET /api/orders endpoint"
```

---

### Task 6: Screenshots router

**Files:**
- Create: `app/api/screenshots.py`
- Test: `app/tests/test_api_screenshots.py`

**Interfaces:**
- Consumes: `settings.DATA_DIR` from `app.settings`.
- Produces: `router` registered by Task 13 as `GET /api/screenshots/{run_id}/{filename}`. Later tasks (Task 7's `_serialize_run`) produce `screenshot_path` values shaped `"{run_id}/{filename}"` that this endpoint's URL directly matches.

- [ ] **Step 1: Write the failing test**

Create `app/tests/test_api_screenshots.py`:

```python
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.screenshots import router as screenshots_router
from app import settings


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_DIR", str(tmp_path))
    shot_dir = tmp_path / "screenshots" / "7"
    shot_dir.mkdir(parents=True)
    (shot_dir / "001_search.png").write_bytes(b"\x89PNG\r\n\x1a\nfakepng")

    app_ = FastAPI()
    app_.include_router(screenshots_router)
    return TestClient(app_)


def test_get_existing_screenshot(client):
    resp = client.get("/api/screenshots/7/001_search.png")
    assert resp.status_code == 200
    assert resp.content == b"\x89PNG\r\n\x1a\nfakepng"
    assert resp.headers["content-type"] == "image/png"


def test_get_missing_screenshot_404(client):
    resp = client.get("/api/screenshots/7/999_missing.png")
    assert resp.status_code == 404


def test_path_traversal_rejected(client):
    resp = client.get("/api/screenshots/7/..%2F..%2Fetc%2Fpasswd.png")
    assert resp.status_code in (400, 404)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "app/.." && python -m pytest app/tests/test_api_screenshots.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.api.screenshots'`

- [ ] **Step 3: Write `app/api/screenshots.py`**

```python
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app import settings

router = APIRouter()

_SAFE_FILENAME = re.compile(r"^[A-Za-z0-9_.\-]+\.png$")


@router.get("/api/screenshots/{run_id}/{filename}")
def get_screenshot(run_id: int, filename: str):
    if not _SAFE_FILENAME.match(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")

    path = Path(settings.DATA_DIR) / "screenshots" / str(run_id) / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Screenshot not found")

    return FileResponse(str(path), media_type="image/png")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "app/.." && python -m pytest app/tests/test_api_screenshots.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add app/api/screenshots.py app/tests/test_api_screenshots.py
git commit -m "feat: add screenshot-serving endpoint with path-traversal guard"
```

---

### Task 7: Runs router (list, detail, start, SSE stream)

This is the most involved router: it must (a) reject starting a new run while one is active, (b) launch the existing synchronous `run_agent(run_id)` on a background thread so the HTTP request returns immediately, (c) guarantee the run never gets stuck in `"running"` forever if the graph raises (today's Streamlit code has no such guard — it would just crash the page; a silent background-thread exception must not permanently block all future runs), and (d) stream progress over SSE by polling the DB.

**Files:**
- Create: `app/api/runs.py`
- Test: `app/tests/test_api_runs.py`

**Interfaces:**
- Consumes: `RunListItem`, `RunDetailOut`, `RunStepOut`, `PlanItemOut`, `RunSummaryOut`, `ItemResultOut`, `StartRunResponse` from Task 2; `Run`, `RunStep`, `Inventory` from `app.db`; `run_agent` from `app.graph.runner`.
- Produces: `router` registered by Task 13 as `POST /api/runs`, `GET /api/runs`, `GET /api/runs/{run_id}`, `GET /api/runs/{run_id}/stream`. The `screenshot_path` values it emits (both in `GET /api/runs/{run_id}` and in SSE `step` events) are shaped `"{run_id}/{filename}"`, matching Task 6's route exactly.

- [ ] **Step 1: Write the failing tests**

Create `app/tests/test_api_runs.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "app/.." && python -m pytest app/tests/test_api_runs.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.api.runs'`

- [ ] **Step 3: Write `app/api/runs.py`**

```python
import json
import threading
import time
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.api.schemas import (
    RunListItem, RunDetailOut, RunStepOut, PlanItemOut, RunSummaryOut,
    ItemResultOut, StartRunResponse,
)
from app.db import get_session, Run, Inventory
from app.graph.runner import run_agent

router = APIRouter()


def _run_worker(run_id: int) -> None:
    try:
        run_agent(run_id)
    except Exception as e:
        with get_session() as session:
            run = session.query(Run).filter(Run.id == run_id).first()
            if run:
                run.status = "failed"
                run.summary_json = {
                    "ordered": 0, "skipped": 0, "failed": 0, "total": 0,
                    "order_number": None, "item_results": [], "error": str(e),
                }


@router.post("/api/runs", response_model=StartRunResponse)
def start_run():
    with get_session() as session:
        active = session.query(Run).filter(Run.status == "running").first()
        if active:
            return StartRunResponse(ok=False, reason="A reorder run is already in progress.")

        low_count = session.query(Inventory).filter(
            (Inventory.qty + Inventory.on_order) < Inventory.reorder_threshold
        ).count()
        if low_count == 0:
            return StartRunResponse(ok=False, reason="All inventory items are adequately stocked. No reorder needed.")

        run = Run(status="running")
        session.add(run)
        session.flush()
        run_id = run.id

    threading.Thread(target=_run_worker, args=(run_id,), daemon=True).start()
    return StartRunResponse(ok=True, run_id=run_id)


@router.get("/api/runs", response_model=list[RunListItem])
def list_runs():
    with get_session() as session:
        runs = session.query(Run).order_by(Run.created_at.desc()).limit(20).all()
        return [RunListItem(id=r.id, created_at=r.created_at, status=r.status) for r in runs]


def _screenshot_url_path(run_id: int, screenshot_path: Optional[str]) -> Optional[str]:
    if not screenshot_path:
        return None
    filename = screenshot_path.replace("\\", "/").rsplit("/", 1)[-1]
    return f"{run_id}/{filename}"


def _serialize_run(run: Run) -> RunDetailOut:
    steps = sorted(run.steps, key=lambda s: (s.seq, s.id))
    return RunDetailOut(
        id=run.id, created_at=run.created_at, status=run.status,
        plan_json=[PlanItemOut(**item) for item in run.plan_json] if run.plan_json else None,
        summary_json=RunSummaryOut(
            ordered=run.summary_json["ordered"], skipped=run.summary_json["skipped"],
            failed=run.summary_json["failed"], total=run.summary_json["total"],
            order_number=run.summary_json.get("order_number"),
            item_results=[ItemResultOut(**r) for r in run.summary_json.get("item_results", [])],
        ) if run.summary_json else None,
        steps=[
            RunStepOut(
                id=s.id, seq=s.seq, label=s.label, detail=s.detail, status=s.status,
                screenshot_path=_screenshot_url_path(run.id, s.screenshot_path),
                reasoning=s.reasoning,
            )
            for s in steps
        ],
    )


@router.get("/api/runs/{run_id}", response_model=Optional[RunDetailOut])
def get_run(run_id: int):
    with get_session() as session:
        run = session.query(Run).filter(Run.id == run_id).first()
        if not run:
            return None
        return _serialize_run(run)


def _sse_frame(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.get("/api/runs/{run_id}/stream")
def stream_run(run_id: int):
    def generate():
        seen_plan = False
        seen_summary = False
        last_status = None
        seen_step_versions = {}

        while True:
            with get_session() as session:
                run = session.query(Run).filter(Run.id == run_id).first()
                if not run:
                    yield _sse_frame("status", {"status": "not_found"})
                    return

                if run.status != last_status:
                    yield _sse_frame("status", {"status": run.status})
                    last_status = run.status

                if run.plan_json and not seen_plan:
                    yield _sse_frame("plan", run.plan_json)
                    seen_plan = True

                steps = sorted(run.steps, key=lambda s: (s.seq, s.id))
                for s in steps:
                    version = (s.status, s.detail, s.screenshot_path, s.reasoning)
                    if seen_step_versions.get(s.id) != version:
                        seen_step_versions[s.id] = version
                        yield _sse_frame("step", {
                            "id": s.id, "seq": s.seq, "label": s.label, "detail": s.detail,
                            "status": s.status,
                            "screenshot_path": _screenshot_url_path(run.id, s.screenshot_path),
                            "reasoning": s.reasoning,
                        })

                if run.summary_json and not seen_summary:
                    yield _sse_frame("summary", run.summary_json)
                    seen_summary = True

                terminal = run.status in ("succeeded", "failed")

            if terminal:
                return
            time.sleep(0.5)

    return StreamingResponse(generate(), media_type="text/event-stream")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "app/.." && python -m pytest app/tests/test_api_runs.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add app/api/runs.py app/tests/test_api_runs.py
git commit -m "feat: add runs API (list, detail, start, SSE stream)"
```

---

### Task 8: mockshop `GET /api/products`

**Files:**
- Modify: `mockshop/main.py`
- Test: `mockshop/tests/test_products_api.py`

**Interfaces:**
- Produces: `GET /api/products` → JSON array of `{id, title, description, price, stock, image_url}` for every catalog row. Task 9 (`app/api/storefront.py`) is the sole consumer, calling this over HTTP via `MOCKSHOP_URL`.

- [ ] **Step 1: Write the failing test**

Create `mockshop/tests/test_products_api.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd mockshop && python -m pytest tests/test_products_api.py -v`
Expected: FAIL with 404 (`assert r.status_code == 200` fails, route doesn't exist)

- [ ] **Step 3: Add the endpoint to `mockshop/main.py`**

Add after the existing `home()` function (which already shows the same query pattern):

```python
@app.get("/api/products")
def api_products():
    from db import _get_conn, _row_to_dict
    conn = _get_conn()
    products = [_row_to_dict(r) for r in conn.execute("SELECT * FROM products ORDER BY id").fetchall()]
    conn.close()
    return products
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd mockshop && python -m pytest tests/test_products_api.py -v`
Expected: PASS

- [ ] **Step 5: Run the full mockshop suite to confirm no regressions**

Run: `cd mockshop && python -m pytest tests/ -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add mockshop/main.py mockshop/tests/test_products_api.py
git commit -m "feat: add GET /api/products to mockshop"
```

---

### Task 9: Storefront router

**Files:**
- Create: `app/api/storefront.py`
- Test: `app/tests/test_api_storefront.py`

**Interfaces:**
- Consumes: `StorefrontInfoOut`, `StorefrontPreviewOut`, `StorefrontProductOut` from Task 2; `settings.MOCKSHOP_URL`. Calls `GET {MOCKSHOP_URL}/api/products` (Task 8's contract) via `httpx.get`, mocked in this task's own test — no need to wait for Task 8 to merge first.
- Produces: `router` registered by Task 13 as `GET /api/storefront`, `GET /api/storefront/preview`.

- [ ] **Step 1: Write the failing test**

Create `app/tests/test_api_storefront.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "app/.." && python -m pytest app/tests/test_api_storefront.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.api.storefront'`

- [ ] **Step 3: Write `app/api/storefront.py`**

```python
import httpx
from fastapi import APIRouter

from app.api.schemas import StorefrontInfoOut, StorefrontPreviewOut, StorefrontProductOut
from app import settings

router = APIRouter()


@router.get("/api/storefront", response_model=StorefrontInfoOut)
def get_storefront_info():
    url = settings.MOCKSHOP_URL.replace("mockshop", "localhost")
    return StorefrontInfoOut(url=url)


@router.get("/api/storefront/preview", response_model=StorefrontPreviewOut)
def get_storefront_preview():
    try:
        resp = httpx.get(f"{settings.MOCKSHOP_URL}/api/products", timeout=5.0)
        resp.raise_for_status()
        products = resp.json()
    except Exception:
        return StorefrontPreviewOut(products=[], total_count=0)

    preview = [
        StorefrontProductOut(
            title=p["title"], price=p["price"],
            stock_badge="In stock" if p["stock"] else "Out of stock",
        )
        for p in products[:6]
    ]
    return StorefrontPreviewOut(products=preview, total_count=len(products))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "app/.." && python -m pytest app/tests/test_api_storefront.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add app/api/storefront.py app/tests/test_api_storefront.py
git commit -m "feat: add storefront info + preview endpoints"
```

---

### Task 10: Docker/deployment configuration

**Files:**
- Modify: `app/Dockerfile`
- Modify: `app/requirements.txt`
- Modify: `docker-compose.yml` (comment/env only — no service topology change)

**Interfaces:**
- Consumes: nothing from other Wave-1 tasks (module path `app.server:app` is fixed by this plan regardless of Task 13's completion order).
- Produces: a container `CMD` that Task 13's `app/server.py` must satisfy (a module-level `app = FastAPI()` object in `app/server.py`).

- [ ] **Step 1: Update `app/requirements.txt`**

Replace the file's contents:

```
sqlalchemy==2.0.35
psycopg2-binary==2.9.9
playwright==1.51.0
langgraph==0.2.44
langchain-anthropic==0.3.2
beautifulsoup4==4.12.3
pytest==8.3.3
pytest-asyncio==0.24.0
anthropic==0.45.0
fastapi>=0.115,<1
uvicorn[standard]>=0.32,<1
httpx>=0.27,<1
```

(`streamlit==1.38.0` removed; `fastapi`, `uvicorn[standard]`, `httpx` added.)

- [ ] **Step 2: Update `app/Dockerfile`'s CMD line**

Change the last line from:

```
CMD ["streamlit", "run", "main.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
```

to:

```
CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8501"]
```

- [ ] **Step 3: Verify docker-compose.yml needs no topology changes**

Read `docker-compose.yml`'s `app` service block — `ports: ["8501:8501"]` and all `environment:` entries (`ANTHROPIC_API_KEY`, `DATABASE_URL`, `MOCKSHOP_URL`, `HEADED`, `DATA_DIR`) stay valid unchanged since the FastAPI app reads the exact same `app/settings.py` env vars the Streamlit app did. No edit needed to `docker-compose.yml` itself — confirm by re-reading the file and checking no `command:` override exists there that would fight the new Dockerfile CMD.

- [ ] **Step 4: Commit**

```bash
git add app/Dockerfile app/requirements.txt
git commit -m "chore: switch app container from Streamlit to Uvicorn/FastAPI"
```

---

### Task 11: `adapter.js` — real endpoint wiring

**Files:**
- Modify: `frontend/adapter.js` (full rewrite)

**Interfaces:**
- Consumes: the documented response shapes from Tasks 3–9 (this task can be written and reviewed independently of those tasks' actual merge order — the shapes are fixed by Task 2's schemas and this plan's endpoint table).
- Produces: every export the `.dc.html` Component imports — `API_BASE`, `getHealth`, `getInventory`, `saveThresholds`, `startRun`, `listRuns`, `getRun`, `listOrders`, `getScreenshotUrl`, `getStorefrontInfo`, `getStorefrontPreview`, `streamRun` — same names/signatures as the mock file so Task 12 and the existing Component code need no changes beyond what Task 12 specifies.

- [ ] **Step 1: Replace `frontend/adapter.js` entirely**

```javascript
// ============================================================================
// VeloRelAI "RPA Order Bot" — API adapter (LIVE MODE)
// ----------------------------------------------------------------------------
// Talks to the FastAPI backend served from the same origin as this file.
// Response shapes match the field names the Component's mock seed data used,
// so the template and renderVals() need no changes beyond Task 12's edits.
// ============================================================================

export const API_BASE = window.location.origin;

async function getJson(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// GET /api/health -> { db_ok, demomart_ok, error? }
export async function getHealth() {
  try {
    return await getJson("/api/health");
  } catch (e) {
    return { db_ok: false, demomart_ok: false, error: e.message || String(e) };
  }
}

// GET /api/inventory -> InventoryItem[] sorted by sku
export function getInventory() {
  return getJson("/api/inventory");
}

// POST /api/inventory/thresholds  body: {sku, reorder_threshold, reorder_qty}[]
export async function saveThresholds(edits) {
  const res = await fetch(`${API_BASE}/api/inventory/thresholds`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(edits),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// POST /api/runs -> {ok:true, run_id} or {ok:false, reason}
export async function startRun() {
  const res = await fetch(`${API_BASE}/api/runs`, { method: "POST" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// GET /api/runs -> {id, created_at, status}[] newest first, limit 20
export function listRuns() {
  return getJson("/api/runs");
}

// GET /api/runs/{id} -> {plan_json, summary_json, status, steps} or null
export function getRun(runId) {
  return getJson(`/api/runs/${runId}`);
}

// GET /api/orders -> newest first
export function listOrders() {
  return getJson("/api/orders");
}

// GET /api/screenshots/{run_id}/{filename} -> real PNG
export function getScreenshotUrl(path) {
  return `${API_BASE}/api/screenshots/${path}`;
}

// GET /api/storefront -> {url}
export function getStorefrontInfo() {
  return getJson("/api/storefront");
}

// GET /api/storefront/preview -> {products, total_count}
export function getStorefrontPreview() {
  return getJson("/api/storefront/preview");
}

// GET /api/runs/{id}/stream (SSE) -> events: plan | step | summary | status
export function streamRun(runId, { onPlan, onStep, onSummary, onStatus }) {
  const controller = new AbortController();

  (async () => {
    try {
      const res = await fetch(`${API_BASE}/api/runs/${runId}/stream`, { signal: controller.signal });
      if (!res.ok || !res.body) return;

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });

        let idx;
        while ((idx = buf.indexOf("\n\n")) !== -1) {
          const frame = buf.slice(0, idx);
          buf = buf.slice(idx + 2);

          const eventMatch = /^event:\s*(.+)$/m.exec(frame);
          const dataMatch = /^data:\s*(.+)$/m.exec(frame);
          if (!eventMatch || !dataMatch) continue;

          const eventName = eventMatch[1].trim();
          let data;
          try {
            data = JSON.parse(dataMatch[1]);
          } catch {
            continue;
          }

          if (eventName === "plan") onPlan && onPlan(data);
          else if (eventName === "step") onStep && onStep(data);
          else if (eventName === "summary") onSummary && onSummary(data);
          else if (eventName === "status") onStatus && onStatus(data);
        }
      }
    } catch (e) {
      if (e.name !== "AbortError") {
        onStatus && onStatus({ status: "failed" });
      }
    }
  })();

  return () => controller.abort();
}
```

- [ ] **Step 2: Verify it's syntactically valid JS**

Run: `node --check "frontend/adapter.js"`
Expected: no output (exit code 0)

- [ ] **Step 3: Commit**

```bash
git add "frontend/adapter.js"
git commit -m "feat: wire adapter.js to real FastAPI endpoints (live mode)"
```

---

### Task 12: `.dc.html` — real screenshots + drop debug hook

**Files:**
- Modify: `frontend/RPA Order Bot.dc.html`

**Interfaces:**
- Consumes: `getScreenshotUrl(path)` from Task 11 (returns a real image URL string given a `"{run_id}/{filename}"` path — this task only needs to know that contract, not Task 11's file itself).
- Produces: no new exports; purely template/markup changes.

- [ ] **Step 1: Replace the timeline screenshot placeholder with a real `<img>`**

Find this block (around line 270-275):

```html
                                    <div style="height:110px;display:flex;align-items:center;justify-content:center;background:repeating-linear-gradient(45deg,{{ T.insetBg }} 0 10px,transparent 10px 20px);position:relative">
                                      <div style="text-align:center">
                                        <div style="font-size:20px;margin-bottom:4px">📷</div>
                                        <div style="font-family:'JetBrains Mono',monospace;font-size:10.5px;color:{{ T.textLo }}">{{ step.label }}</div>
                                      </div>
                                    </div>
```

Replace with:

```html
                                    <div style="height:110px;display:flex;align-items:center;justify-content:center;background:repeating-linear-gradient(45deg,{{ T.insetBg }} 0 10px,transparent 10px 20px);position:relative;overflow:hidden">
                                      <img src="{{ step.shotUrl }}" alt="Screenshot: {{ step.label }}" style="width:100%;height:100%;object-fit:cover;display:block" onError="this.style.display='none';this.nextSibling.style.display='flex'" />
                                      <div style="display:none;text-align:center;position:absolute;inset:0;align-items:center;justify-content:center;flex-direction:column">
                                        <div style="font-size:20px;margin-bottom:4px">📷</div>
                                        <div style="font-family:'JetBrains Mono',monospace;font-size:10.5px;color:{{ T.textLo }}">{{ step.label }}</div>
                                      </div>
                                    </div>
```

- [ ] **Step 2: Replace the lightbox placeholder with a real `<img>`**

Find this block (around line 446):

```html
                        <div style="text-align:center"><div style="font-size:32px;margin-bottom:8px">📷</div><div style="font-family:'JetBrains Mono',monospace;font-size:13px;color:{{ T.textLo }}">{{ lightboxLabel }}</div></div>
```

Replace with:

```html
                        <img src="{{ lightboxUrl }}" alt="{{ lightboxLabel }}" style="max-width:100%;max-height:70vh;display:block;margin:0 auto" onError="this.style.display='none';this.nextSibling.style.display='block'" />
                        <div style="display:none;text-align:center"><div style="font-size:32px;margin-bottom:8px">📷</div><div style="font-family:'JetBrains Mono',monospace;font-size:13px;color:{{ T.textLo }}">{{ lightboxLabel }}</div></div>
```

- [ ] **Step 3: Add `shotUrl` to the per-step view-model in `renderVals()`**

Find (around line 737-742):

```javascript
        steps: groupsMap[gk].map((st) => ({
          ...st, dotColor: STATUS_COLOR[st.status] || '#6b7280', dotAnim: st.status === 'running' ? 'pulseHalo 1.3s infinite' : 'none',
          statusLabel: st.status, badgeColor: STATUS_COLOR[st.status] || '#6b7280',
          hasDetail: !!st.detail, hasReasoning: !!st.reasoning, hasShot: !!st.screenshot_path,
          shotSlug: st.screenshot_path || '', openShot: () => this.openLightbox(st.seq),
        })),
```

Replace with:

```javascript
        steps: groupsMap[gk].map((st) => ({
          ...st, dotColor: STATUS_COLOR[st.status] || '#6b7280', dotAnim: st.status === 'running' ? 'pulseHalo 1.3s infinite' : 'none',
          statusLabel: st.status, badgeColor: STATUS_COLOR[st.status] || '#6b7280',
          hasDetail: !!st.detail, hasReasoning: !!st.reasoning, hasShot: !!st.screenshot_path,
          shotSlug: st.screenshot_path || '', shotUrl: st.screenshot_path ? this.api.getScreenshotUrl(st.screenshot_path) : '',
          openShot: () => this.openLightbox(st.seq),
        })),
```

- [ ] **Step 4: Add `lightboxUrl` next to the existing `lightboxSlug` computation**

Find (around line 829-830):

```javascript
      lightboxOpen: !!s.lightbox, lightboxSlug: lightboxStep?.screenshot_path || '', lightboxLabel: lightboxStep?.label || '',
```

Replace with:

```javascript
      lightboxOpen: !!s.lightbox, lightboxSlug: lightboxStep?.screenshot_path || '', lightboxLabel: lightboxStep?.label || '',
      lightboxUrl: lightboxStep?.screenshot_path ? this.api.getScreenshotUrl(lightboxStep.screenshot_path) : '',
```

- [ ] **Step 5: Remove the debug health-toggle hook**

Find and delete the Ctrl+Shift+H binding (around line 500) and the `__debugToggleDemomart` reference — search for `__debugToggleDemomart` in the file and remove the keydown handler branch that calls it (leave the rest of the keydown handler, e.g. the lightbox arrow-key handling, untouched).

- [ ] **Step 6: Visually smoke-test in isolation**

Run: `python3 -m http.server 8099 --directory frontend` then open `http://localhost:8099/RPA%20Order%20Bot.dc.html` in a browser — since `adapter.js` now points at `window.location.origin` with no backend yet running there, expect network errors in the console but the page should still render its shell (empty states) without a JS crash. This is just a template-syntax sanity check; full behavior is verified in Task 15.

- [ ] **Step 7: Commit**

```bash
git add "frontend/RPA Order Bot.dc.html"
git commit -m "feat: render real screenshots in run timeline and lightbox"
```

---

### Task 13: `app/server.py` — assemble the FastAPI app

**Files:**
- Create: `app/server.py`
- Test: `app/tests/test_server_smoke.py`

**Interfaces:**
- Consumes: every router from Tasks 3, 4, 5, 6, 7, 9 (`health_router`, `inventory_router`, `orders_router`, `screenshots_router`, `runs_router`, `storefront_router`); `init_db`, `seed_inventory` from `app.db`.
- Produces: `app` (the FastAPI instance referenced by Task 10's Docker `CMD` as `app.server:app`).

- [ ] **Step 1: Write the failing smoke test**

Create `app/tests/test_server_smoke.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "app/.." && python -m pytest app/tests/test_server_smoke.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.server'`

- [ ] **Step 3: Write `app/server.py`**

```python
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.health import router as health_router
from app.api.inventory import router as inventory_router
from app.api.orders import router as orders_router
from app.api.runs import router as runs_router
from app.api.screenshots import router as screenshots_router
from app.api.storefront import router as storefront_router
from app.db import init_db, get_session, seed_inventory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
INDEX_FILE = FRONTEND_DIR / "RPA Order Bot.dc.html"

app = FastAPI(title="RPA Order Bot")


@app.on_event("startup")
def _startup() -> None:
    init_db()
    with get_session() as session:
        seed_inventory(session)


# API routers (registered before the catch-all static mount so they take
# precedence over file serving).
app.include_router(health_router)
app.include_router(inventory_router)
app.include_router(orders_router)
app.include_router(runs_router)
app.include_router(screenshots_router)
app.include_router(storefront_router)


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(INDEX_FILE)


# Serve the dc-runtime frontend (support.js, adapter.js, uploads/*) from the
# same origin as the API.
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd "app/.." && python -m pytest app/tests/test_server_smoke.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the entire Python test suite (app + mockshop) to confirm zero regressions**

Run: `cd "app/.." && python -m pytest app/tests/ -v && cd mockshop && python -m pytest tests/ -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add app/server.py app/tests/test_server_smoke.py
git commit -m "feat: assemble FastAPI app serving API + dc-runtime frontend"
```

---

### Task 14: Delete Streamlit-only files

Only proceed once Task 13's smoke tests and Task 15's E2E check both pass — this task removes the old UI's entry point and tab modules now that every piece of functionality has a real API equivalent.

**Files:**
- Delete: `app/main.py`
- Delete: `app/tabs/inventory.py`, `app/tabs/run.py`, `app/tabs/orders.py`, `app/tabs/storefront.py`
- Delete: `app/tabs/__init__.py` (if it contains only Streamlit-tab wiring — check its contents first)

**Interfaces:** none — this task produces no new interfaces, it only removes dead code superseded by Tasks 3–9.

- [ ] **Step 1: Confirm nothing else imports the tab modules**

Run: `cd "app/.." && grep -rn "from app.tabs\|import app.tabs" --include="*.py" app/ | grep -v "app/tabs/"`
Expected: no output (only `app/main.py` itself references `app.tabs`, and it's being deleted too)

- [ ] **Step 2: Delete the files**

```bash
git rm app/main.py app/tabs/inventory.py app/tabs/run.py app/tabs/orders.py app/tabs/storefront.py app/tabs/__init__.py
```

- [ ] **Step 3: Run the full Python test suite once more**

Run: `cd "app/.." && python -m pytest app/tests/ -v`
Expected: all PASS (no test imported the deleted Streamlit modules — they were UI-only, untested render functions)

- [ ] **Step 4: Commit**

```bash
git commit -m "chore: remove Streamlit UI now superseded by FastAPI + dc-runtime frontend"
```

---

### Task 15: End-to-end Docker verification

**Files:** none created or modified — this task only runs and observes the stack.

- [ ] **Step 1: Build and start the full stack**

Run: `docker compose up --build -d`
Expected: all three services (`db`, `mockshop`, `app`) report healthy/running; `docker compose ps` shows no restart loops.

- [ ] **Step 2: Confirm the frontend loads**

Run: `curl -s -o /dev/null -w "%{http_code}" http://localhost:8501/`
Expected: `200`

- [ ] **Step 3: Confirm each API endpoint responds**

Run:
```bash
curl -s http://localhost:8501/api/health
curl -s http://localhost:8501/api/inventory
curl -s http://localhost:8501/api/orders
curl -s http://localhost:8501/api/runs
curl -s http://localhost:8501/api/storefront
curl -s http://localhost:8501/api/storefront/preview
```
Expected: each returns valid JSON matching the shapes from Task 2's schemas (inventory has 10 items, storefront preview has 6 products with `total_count: 25`).

- [ ] **Step 4: Exercise the full reorder flow through the real browser UI**

Open `http://localhost:8501` in a browser. On the Inventory tab, confirm 3 low-stock rows are highlighted. Click "Run Reorder Agent" and confirm: the launch overlay appears, the Run tab shows a live-updating plan card and timeline (real Claude + Playwright activity against `mockshop`), screenshots render as actual images (not camera-icon placeholders) in both the timeline and the lightbox, the summary counts animate in, and an order number banner appears. Confirm the Orders tab then shows the new order, and the Inventory tab's "On Order" column updates.

- [ ] **Step 5: Confirm run concurrency guard**

While a run is in progress, attempt to trigger another run (e.g. via `curl -s -X POST http://localhost:8501/api/runs`) and confirm the response is `{"ok": false, "reason": "A reorder run is already in progress."}`.

- [ ] **Step 6: Tear down**

Run: `docker compose down` (add `-v` only if you intend to reset seed data/screenshots for a clean demo state — confirm with the user before using `-v`, since it deletes the Postgres volume and any previously placed demo orders).

---

## Self-Review Notes

- **Spec coverage:** every endpoint in the design spec's table (health, inventory, thresholds, runs list/detail/start/stream, orders, screenshots, storefront info/preview) has a task. The `reasoning` persistence gap discovered while cross-referencing `browse.py` against the frontend template (Task 1) was not in the original spec's endpoint table but is required for the spec's screenshot/timeline behavior to be honest about what data really exists — added explicitly rather than silently dropping the "AI explains its reasoning" behavior the frontend already renders.
- **Concurrency correctness:** the spec called for rejecting concurrent runs; Task 7 additionally guards against a run getting permanently stuck at `status="running"` if the background thread's `run_agent()` call raises — this didn't exist in the Streamlit version (which crashed visibly instead of failing silently in a background thread) and is a correctness requirement of moving execution off the request thread, not scope creep.
- **Type consistency:** `screenshot_path` is produced as `"{run_id}/{filename}"` by Task 7 (both `GET /api/runs/{id}` and the SSE `step` event) and consumed by Task 6's route `GET /api/screenshots/{run_id}/{filename}` and Task 11's `getScreenshotUrl(path)` — verified consistent across all three.
- **Out of scope confirmed:** `app/scripted_run.py` is untouched by every task above.
