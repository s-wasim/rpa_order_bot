from playwright.sync_api import Page, expect

from app.settings import MOCKSHOP_URL
from app.steps import StepError


def add_to_cart(page: Page, product_url: str, quantity: int) -> dict:
    page.goto(product_url)
    page.fill("[data-testid='qty-input']", str(quantity))
    page.click("[data-testid='add-to-cart']")

    expect(page).to_have_url(MOCKSHOP_URL + "/cart")

    cart_title_els = page.locator("[data-testid='cart-item-title']")
    cart_qty_els = page.locator("[data-testid='cart-item-qty']")
    count = cart_title_els.count()
    cart_items = []
    for i in range(count):
        title = cart_title_els.nth(i).inner_text()
        qty_val = cart_qty_els.nth(i).input_value()
        cart_items.append({"title": title.strip(), "qty": int(qty_val)})

    if not cart_items:
        raise StepError("Cart is empty after adding product")

    return {"success": True, "cart_items": cart_items}
