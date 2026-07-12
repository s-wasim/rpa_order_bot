from unittest.mock import MagicMock, patch

import pytest
from playwright.sync_api import expect

from app.steps.cart import add_to_cart
from app.steps import StepError


@pytest.fixture
def mock_page():
    page = MagicMock()

    title_locator = MagicMock()
    title_locator.count.return_value = 1
    title_locator.nth.return_value.inner_text.return_value = "ArcticBond TX-4 Thermal Compound, 4 g"

    qty_locator = MagicMock()
    qty_locator.count.return_value = 1
    qty_locator.nth.return_value.input_value.return_value = "3"

    page.locator.side_effect = lambda sel: {
        "[data-testid='cart-item-title']": title_locator,
        "[data-testid='cart-item-qty']": qty_locator,
    }.get(sel, MagicMock())

    return page


def test_add_to_cart_success(mock_page):
    with patch("app.steps.cart.MOCKSHOP_URL", "http://mockshop:8090"), patch("app.steps.cart.expect"):
        result = add_to_cart(mock_page, "http://mockshop:8090/product/1", 3)

    assert result["success"] is True
    assert len(result["cart_items"]) == 1
    assert result["cart_items"][0]["title"] == "ArcticBond TX-4 Thermal Compound, 4 g"
    assert result["cart_items"][0]["qty"] == 3


def test_add_to_cart_empty_cart_raises_error(mock_page):
    empty_title_locator = MagicMock()
    empty_title_locator.count.return_value = 0

    def locator_side_effect(sel):
        if sel == "[data-testid='cart-item-title']":
            return empty_title_locator
        return MagicMock()

    mock_page.locator.side_effect = locator_side_effect

    with patch("app.steps.cart.MOCKSHOP_URL", "http://mockshop:8090"), patch("app.steps.cart.expect"):
        with pytest.raises(StepError, match="Cart is empty"):
            add_to_cart(mock_page, "http://mockshop:8090/product/1", 3)
