from typing import TypedDict, Optional


class PlanItem(TypedDict):
    sku: str
    name: str
    search_terms: str
    quantity: int
    notes: str


class ItemResult(TypedDict):
    sku: str
    name: str
    status: str
    reasoning: str
    product_title: Optional[str]
    unit_price: Optional[float]
    quantity: int


class OrderState(TypedDict):
    run_id: int
    low_stock: list[dict]
    plan: Optional[list[PlanItem]]
    current_index: int
    item_results: list[ItemResult]
    order_number: Optional[str]
    screenshots: list[str]
    error: Optional[str]
