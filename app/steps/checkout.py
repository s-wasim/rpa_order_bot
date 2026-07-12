import re

from playwright.sync_api import Page, expect
from playwright.sync_api import TimeoutError as PwTimeout

from app.settings import MOCKSHOP_URL
from app.steps import StepError


def checkout(page: Page) -> str:
    page.goto(MOCKSHOP_URL + "/checkout")

    page.fill("[data-testid='checkout-name']", "Demo Company")
    page.fill("[data-testid='checkout-email']", "demo@example.com")
    page.fill("[data-testid='checkout-phone']", "+1-555-0123")
    page.fill("[data-testid='checkout-address']", "123 Business Park Drive")

    page.click("[data-testid='checkout-submit']")

    try:
        expect(page).to_have_url(re.compile(r"/confirm/DM-\d{5}"))
    except (PwTimeout, AssertionError):
        raise StepError("Checkout did not redirect to confirmation page")

    order_el = page.locator("[data-testid='order-number']")
    order_text = order_el.inner_text().strip()
    match = re.search(r"DM-\d{5}", order_text)
    if not match:
        raise StepError(f"Could not extract order number from: {order_text}")
    order_number = match.group(0)

    return order_number
