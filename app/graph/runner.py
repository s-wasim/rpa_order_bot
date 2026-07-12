from app.graph.build import run_graph
from app.graph.state import OrderState


def run_agent(run_id: int) -> dict:
    """Invoke the LangGraph reorder agent for a run and return a summary dict.

    The graph loads low-stock inventory, plans with Claude, browses/matches each
    item, checks out matched items, and records the order + inventory updates.
    Detailed timeline steps and the summary are persisted to the DB by the nodes.
    """
    initial_state: OrderState = {
        "run_id": run_id,
        "low_stock": [],
        "plan": None,
        "current_index": 0,
        "item_results": [],
        "order_number": None,
        "screenshots": [],
        "error": None,
    }

    final_state = run_graph.invoke(initial_state)

    item_results = final_state.get("item_results", [])
    ordered = sum(1 for r in item_results if r["status"] == "matched")
    skipped = sum(1 for r in item_results if r["status"] == "skipped")
    failed = sum(1 for r in item_results if r["status"] == "failed")

    return {
        "status": "succeeded",
        "ordered": ordered,
        "skipped": skipped,
        "failed": failed,
        "order_number": final_state.get("order_number"),
    }
