import re
from unittest.mock import MagicMock, patch

import pytest
from playwright.sync_api import expect

from app.steps.checkout import checkout


@pytest.fixture
def mock_page():
    page = MagicMock()

    order_el = MagicMock()
    order_el.inner_text.return_value = "DM-12345"
    page.locator.return_value = order_el

    return page


def test_checkout_extracts_order_number(mock_page):
    with patch("app.steps.checkout.MOCKSHOP_URL", "http://mockshop:8090"), patch("app.steps.checkout.expect"):
        order_no = checkout(mock_page)

    assert order_no == "DM-12345"

    mock_page.goto.assert_called_once_with("http://mockshop:8090/checkout")
    mock_page.fill.assert_any_call("[data-testid='checkout-name']", "Demo Company")
    mock_page.fill.assert_any_call("[data-testid='checkout-email']", "demo@example.com")
    mock_page.fill.assert_any_call("[data-testid='checkout-phone']", "+1-555-0123")
    mock_page.fill.assert_any_call("[data-testid='checkout-address']", "123 Business Park Drive")
    mock_page.click.assert_called_once_with("[data-testid='checkout-submit']")


def test_checkout_order_number_format(mock_page):
    from app.steps import StepError

    bad_el = MagicMock()
    bad_el.inner_text.return_value = "Order #ABC-123"
    mock_page.locator.return_value = bad_el

    with patch("app.steps.checkout.MOCKSHOP_URL", "http://mockshop:8090"), patch("app.steps.checkout.expect"):
        with pytest.raises(StepError, match="Could not extract order number"):
            checkout(mock_page)


def test_dm_xxxxx_regex():
    assert re.search(r"DM-\d{5}", "DM-12345") is not None
    assert re.search(r"DM-\d{5}", "Order DM-99999 placed") is not None
    assert re.search(r"DM-\d{5}", "DM-1234") is None
    assert re.search(r"DM-\d{5}", "DM-123456") is not None
