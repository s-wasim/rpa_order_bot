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
