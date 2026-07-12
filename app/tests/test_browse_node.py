from unittest.mock import MagicMock, patch, call

import pytest

from app.graph.nodes.browse import browse_and_match_item
from app.graph.state import OrderState, PlanItem
from app.steps import StepError


@pytest.fixture
def state() -> OrderState:
    return {
        "run_id": 1,
        "low_stock": [
            {"sku": "THERMAL-PASTE-001", "name": "Thermal Paste 4g Tube",
             "qty": 2, "reorder_threshold": 5, "reorder_qty": 10, "on_order": 0},
            {"sku": "NO-MATCH-008", "name": "Proprietary Connector Kit",
             "qty": 1, "reorder_threshold": 3, "reorder_qty": 3, "on_order": 0},
        ],
        "plan": [
            {"sku": "THERMAL-PASTE-001", "name": "Thermal Paste 4g Tube",
             "search_terms": "thermal paste", "quantity": 10, "notes": ""},
            {"sku": "NO-MATCH-008", "name": "Proprietary Connector Kit",
             "search_terms": "connector kit", "quantity": 3, "notes": ""},
        ],
        "current_index": 0,
        "item_results": [],
        "order_number": None,
        "screenshots": [],
        "error": None,
    }


@patch("app.graph.nodes.browse.get_registry")
@patch("app.graph.nodes.browse.search_product")
@patch("app.graph.nodes.browse.match_product")
@patch("app.graph.nodes.browse.add_to_cart")
@patch("app.graph.nodes.browse.get_session")
@patch("app.graph.nodes.browse.take_screenshot")
def test_browse_skip_on_no_match(
    mock_ss, mock_session, mock_cart, mock_match, mock_search, mock_registry, state
):
    mock_page = MagicMock()
    mock_registry.return_value.get_page.return_value = mock_page

    mock_search.return_value = [{"title": "Some Product", "price": 9.99, "url": "/product/1"}]
    mock_match.return_value = {"choice_index": None, "confidence": 0.0, "reasoning": "No clear match"}

    result = browse_and_match_item(state)

    assert result["current_index"] == 1
    assert len(result["item_results"]) == 1
    assert result["item_results"][0]["status"] == "skipped"
    mock_cart.assert_not_called()


@patch("app.graph.nodes.browse.get_registry")
@patch("app.graph.nodes.browse.search_product")
@patch("app.graph.nodes.browse.match_product")
@patch("app.graph.nodes.browse.add_to_cart")
@patch("app.graph.nodes.browse.get_session")
@patch("app.graph.nodes.browse.take_screenshot")
def test_browse_retry_on_steperror(
    mock_ss, mock_session, mock_cart, mock_match, mock_search, mock_registry, state
):
    mock_page = MagicMock()
    mock_registry.return_value.get_page.return_value = mock_page

    mock_search.return_value = [{"title": "ArcticBond TX-4", "price": 8.99, "url": "/product/1"}]
    mock_match.return_value = {"choice_index": 0, "confidence": 0.95, "reasoning": "Good match"}
    mock_cart.side_effect = [StepError("First attempt failed"), {"success": True, "cart_items": []}]

    result = browse_and_match_item(state)

    assert result["current_index"] == 1
    assert result["item_results"][0]["status"] == "matched"
    assert mock_cart.call_count == 2


@patch("app.graph.nodes.browse.get_registry")
@patch("app.graph.nodes.browse.search_product")
@patch("app.graph.nodes.browse.match_product")
@patch("app.graph.nodes.browse.add_to_cart")
@patch("app.graph.nodes.browse.get_session")
@patch("app.graph.nodes.browse.take_screenshot")
def test_browse_fails_after_retry(
    mock_ss, mock_session, mock_cart, mock_match, mock_search, mock_registry, state
):
    mock_page = MagicMock()
    mock_registry.return_value.get_page.return_value = mock_page

    mock_search.return_value = [{"title": "ArcticBond TX-4", "price": 8.99, "url": "/product/1"}]
    mock_match.return_value = {"choice_index": 0, "confidence": 0.95, "reasoning": "Good match"}
    mock_cart.side_effect = StepError("Always fails")

    result = browse_and_match_item(state)

    assert result["current_index"] == 1
    assert result["item_results"][0]["status"] == "failed"
    assert mock_cart.call_count == 2
