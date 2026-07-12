from langgraph.graph import StateGraph, END

from app.browser import create_context, close_context
from app.db import get_session
from app.db import Inventory, Run, RunStep
from app.graph.registry import get_registry
from app.graph.state import OrderState
from app.graph.nodes.plan import plan_node
from app.graph.nodes.browse import browse_and_match_item
from app.graph.nodes.checkout_node import checkout_node
from app.graph.nodes.record import record_order


def load_inventory(state: OrderState) -> OrderState:
    with get_session() as session:
        low_stock = (
            session.query(Inventory)
            .filter(Inventory.qty + Inventory.on_order < Inventory.reorder_threshold)
            .all()
        )
    items = [
        {
            "sku": i.sku,
            "name": i.name,
            "qty": i.qty,
            "reorder_threshold": i.reorder_threshold,
            "reorder_qty": i.reorder_qty,
            "on_order": i.on_order,
        }
        for i in low_stock
    ]

    from app.settings import HEADED
    context = create_context(headless=not HEADED)
    page = context.pages[0] if context.pages else context.new_page()
    registry = get_registry()
    registry.set_context(context)
    registry.set_page(page)

    return {
        **state,
        "low_stock": items,
        "plan": None,
        "current_index": 0,
        "item_results": [],
        "order_number": None,
        "screenshots": [],
        "error": None,
    }


def finish_empty(state: OrderState) -> OrderState:
    registry = get_registry()
    registry.close()
    return state


def has_items(state: OrderState) -> str:
    """Loop guard: are there still plan items left to browse?"""
    if state.get("plan") and state["current_index"] < len(state["plan"]):
        return "browse"
    return "check_cart"


def has_plan(state: OrderState) -> str:
    """After planning: did we produce any plan items to browse?"""
    if state.get("plan") and len(state["plan"]) > 0:
        return "browse"
    return "empty"


def anything_in_cart(state: OrderState) -> str:
    """Terminal branch: did at least one item make it into the cart?"""
    matched = any(r["status"] == "matched" for r in state.get("item_results", []))
    if matched:
        return "checkout"
    return "empty"


def route_after_load(state: OrderState) -> str:
    """Entry branch: only plan if there is low stock to reorder."""
    return "plan" if state.get("low_stock") else "empty"


def route_after_browse(state: OrderState) -> str:
    """Loop back while items remain, otherwise decide checkout vs empty."""
    if has_items(state) == "browse":
        return "browse"
    return anything_in_cart(state)


builder = StateGraph(OrderState)

builder.add_node("load_inventory", load_inventory)
builder.add_node("plan_purchases", plan_node)
builder.add_node("browse_and_match_item", browse_and_match_item)
builder.add_node("checkout", checkout_node)
builder.add_node("record_order", record_order)
builder.add_node("finish_empty", finish_empty)

builder.set_entry_point("load_inventory")

builder.add_conditional_edges(
    "load_inventory",
    route_after_load,
    {"plan": "plan_purchases", "empty": "finish_empty"},
)

builder.add_conditional_edges(
    "plan_purchases",
    has_plan,
    {"browse": "browse_and_match_item", "empty": "finish_empty"},
)

builder.add_conditional_edges(
    "browse_and_match_item",
    route_after_browse,
    {
        "browse": "browse_and_match_item",
        "checkout": "checkout",
        "empty": "finish_empty",
    },
)

builder.add_edge("checkout", "record_order")
builder.add_edge("record_order", END)
builder.add_edge("finish_empty", END)

run_graph = builder.compile()
