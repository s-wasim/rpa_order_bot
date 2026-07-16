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
