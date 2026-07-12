from datetime import datetime, timezone

from app.db import get_session
from app.db import Inventory, Run, Order, OrderItem
from app.graph.state import OrderState


def record_order(state: OrderState) -> OrderState:
    with get_session() as session:
        run = session.query(Run).filter(Run.id == state["run_id"]).first()
        if not run:
            return {**state, "error": "Run not found"}

        item_results = state.get("item_results", [])
        matched = [r for r in item_results if r["status"] == "matched"]
        skipped = [r for r in item_results if r["status"] == "skipped"]
        failed = [r for r in item_results if r["status"] == "failed"]

        total_ordered = sum(m["quantity"] * (m["unit_price"] or 0) for m in matched)

        if state.get("order_number") and matched:
            order = Order(
                run_id=state["run_id"],
                demomart_order_no=state["order_number"],
                total=total_ordered,
                created_at=datetime.now(timezone.utc),
            )
            session.add(order)
            session.flush()

            for m in matched:
                order_item = OrderItem(
                    order_id=order.id,
                    sku=m["sku"],
                    product_title=m["product_title"] or m["name"],
                    qty=m["quantity"],
                    unit_price=m["unit_price"] or 0,
                )
                session.add(order_item)

                inv = session.query(Inventory).filter(Inventory.sku == m["sku"]).first()
                if inv:
                    inv.on_order = (inv.on_order or 0) + m["quantity"]

        summary = {
            "ordered": len(matched),
            "skipped": len(skipped),
            "failed": len(failed),
            "total": total_ordered,
            "order_number": state.get("order_number"),
            "item_results": [
                {
                    "sku": r["sku"],
                    "name": r["name"],
                    "status": r["status"],
                    "reasoning": r["reasoning"],
                    "qty": r["quantity"],
                }
                for r in item_results
            ],
        }

        run.status = "succeeded"
        run.summary_json = summary

    return {
        **state,
        "error": None,
    }
