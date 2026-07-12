from datetime import datetime, timezone

from app.browser import create_context, close_context, take_screenshot
from app.db import get_session
from app.db import Inventory, Run, RunStep, Order, OrderItem
from app.llm import get_llm
from app.settings import HEADED, MOCKSHOP_URL
from app.steps.search import search_product
from app.steps.match import match_product
from app.steps.cart import add_to_cart
from app.steps.checkout import checkout


def run_scripted(run_id: int) -> dict:
    with get_session() as session:
        low_stock = (
            session.query(Inventory)
            .filter(Inventory.qty + Inventory.on_order < Inventory.reorder_threshold)
            .all()
        )
        low_stock_dicts = [
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

    if not low_stock_dicts:
        return {"status": "skipped", "reason": "No low-stock items"}

    context = create_context(headless=not HEADED)
    page = context.pages[0] if context.pages else context.new_page()

    seq = 0
    matched_items = []
    total_price = 0.0

    def save_step(label, detail, status, screenshot_path=None):
        nonlocal seq
        seq += 1
        with get_session() as session:
            step = RunStep(
                run_id=run_id,
                seq=seq,
                label=label,
                detail=detail,
                status=status,
                screenshot_path=screenshot_path,
            )
            session.add(step)

    save_step("Start Scripted Run", f"Found {len(low_stock_dicts)} low-stock items", "running")

    llm = get_llm()
    first = low_stock_dicts[0]

    save_step(f"Search for {first['name']}", f"Searching: {first['name']}", "running")
    candidates = search_product(page, first["name"])
    ss = take_screenshot(page, run_id, seq, f"search_{first['sku']}")

    if not candidates:
        save_step(f"No results for {first['name']}", "Search returned zero results", "skipped", ss)
    else:
        match_result = match_product(llm, first, candidates)
        choice = match_result["choice_index"]
        reasoning = match_result["reasoning"]

        if choice is not None and choice < len(candidates):
            candidate = candidates[choice]
            try:
                cart_result = add_to_cart(page, candidate["url"], first["reorder_qty"])
                ss2 = take_screenshot(page, run_id, seq, f"cart_{first['sku']}")
                save_step(
                    f"Added {first['name']} to cart",
                    f"{first['reorder_qty']}× {candidate['title']} @ ${candidate['price']:.2f}",
                    "succeeded", ss2,
                )
                matched_items.append({
                    "sku": first["sku"],
                    "name": first["name"],
                    "title": candidate["title"],
                    "qty": first["reorder_qty"],
                    "price": candidate["price"],
                })
                total_price += candidate["price"] * first["reorder_qty"]
            except Exception as e:
                save_step(f"Cart failed for {first['name']}", str(e), "failed", ss)
        else:
            save_step(f"Skipped {first['name']}", f"No match: {reasoning}", "skipped", ss)

    order_number = None
    if matched_items:
        try:
            order_number = checkout(page)
            ss3 = take_screenshot(page, run_id, seq, "confirmation")
            save_step("Checkout complete", f"Order {order_number} placed", "succeeded", ss3)
        except Exception as e:
            save_step("Checkout failed", str(e), "failed")

    with get_session() as session:
        run = session.query(Run).filter(Run.id == run_id).first()
        if run:
            run.status = "succeeded"
            summary = {
                "ordered": len(matched_items),
                "skipped": len(low_stock_dicts) - len(matched_items),
                "failed": 0,
                "total": total_price,
                "order_number": order_number,
            }
            run.summary_json = summary

        for m in matched_items:
            order = Order(
                run_id=run_id,
                demomart_order_no=order_number or "N/A",
                total=total_price,
                created_at=datetime.now(timezone.utc),
            )
            session.add(order)
            session.flush()

            order_item = OrderItem(
                order_id=order.id,
                sku=m["sku"],
                product_title=m["title"],
                qty=m["qty"],
                unit_price=m["price"],
            )
            session.add(order_item)

            inv = session.query(Inventory).filter(Inventory.sku == m["sku"]).first()
            if inv:
                inv.on_order = (inv.on_order or 0) + m["qty"]

    close_context(context)

    return {
        "status": "succeeded",
        "ordered": len(matched_items),
        "skipped": len(low_stock_dicts) - len(matched_items),
        "order_number": order_number,
    }
