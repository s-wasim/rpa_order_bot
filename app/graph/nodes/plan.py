from typing import Optional

from pydantic import BaseModel, Field

from app.db import get_session
from app.db import Run
from app.llm import get_llm
from app.graph.state import OrderState, PlanItem


class PlanItemModel(BaseModel):
    sku: str = Field(description="SKU of the inventory item")
    name: str = Field(description="Name of the inventory item")
    search_terms: str = Field(description="What to search on the storefront")
    quantity: int = Field(description="Quantity to order (reorder_qty)")
    notes: str = Field(description="Any notes about this item")


class Plan(BaseModel):
    items: list[PlanItemModel]


def plan_node(state: OrderState) -> OrderState:
    llm = get_llm()
    structured_llm = llm.with_structured_output(Plan)

    lines = ["You are a purchasing agent building a shopping plan.\n"]
    lines.append("Inventory items needing replenishment (low stock):")
    for item in state["low_stock"]:
        lines.append(
            f"  - SKU: {item['sku']}, Name: {item['name']}, "
            f"Qty: {item['qty']}, Reorder Qty: {item['reorder_qty']}"
        )
    lines.append(
        "\nCreate a shopping plan covering every low-stock SKU exactly once. "
        "For each item, suggest search terms to find it on the storefront."
    )

    prompt = "\n".join(lines)
    plan_result = structured_llm.invoke(prompt)

    plan: list[PlanItem] = [
        {
            "sku": p.sku,
            "name": p.name,
            "search_terms": p.search_terms,
            "quantity": p.quantity,
            "notes": p.notes,
        }
        for p in plan_result.items
    ]

    with get_session() as session:
        run = session.query(Run).filter(Run.id == state["run_id"]).first()
        if run:
            run.plan_json = plan

    return {
        **state,
        "plan": plan,
        "current_index": 0,
    }
