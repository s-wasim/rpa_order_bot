from app.browser import take_screenshot
from app.db import get_session
from app.db import RunStep
from app.graph.registry import get_registry
from app.graph.state import OrderState
from app.steps.checkout import checkout


def checkout_node(state: OrderState) -> OrderState:
    page = get_registry().get_page()

    matched = [r for r in state.get("item_results", []) if r["status"] == "matched"]
    if not matched:
        return {**state, "order_number": None}

    order_number = checkout(page)
    ss = take_screenshot(page, state["run_id"], 900, "confirmation")

    with get_session() as session:
        session.add(RunStep(
            run_id=state["run_id"],
            seq=900,
            label="Checkout complete",
            detail=f"Order {order_number} placed for {len(matched)} item(s)",
            status="succeeded",
            screenshot_path=ss,
        ))

    return {
        **state,
        "order_number": order_number,
        "screenshots": [*state.get("screenshots", []), ss],
    }
