from unittest.mock import MagicMock, patch

import pytest

from app.graph.state import OrderState, PlanItem, ItemResult


@pytest.fixture
def sample_state() -> OrderState:
    return {
        "run_id": 1,
        "low_stock": [
            {"sku": "THERMAL-PASTE-001", "name": "Thermal Paste 4g Tube", "qty": 2,
             "reorder_threshold": 5, "reorder_qty": 10, "on_order": 0},
            {"sku": "MECH-KEYB-003", "name": "Mechanical Keyboard", "qty": 1,
             "reorder_threshold": 3, "reorder_qty": 3, "on_order": 0},
            {"sku": "NO-MATCH-008", "name": "Proprietary Connector Kit", "qty": 1,
             "reorder_threshold": 3, "reorder_qty": 3, "on_order": 0},
        ],
        "plan": [
            {"sku": "THERMAL-PASTE-001", "name": "Thermal Paste 4g Tube",
             "search_terms": "thermal paste", "quantity": 10, "notes": ""},
            {"sku": "MECH-KEYB-003", "name": "Mechanical Keyboard",
             "search_terms": "mechanical keyboard", "quantity": 3, "notes": ""},
            {"sku": "NO-MATCH-008", "name": "Proprietary Connector Kit",
             "search_terms": "connector kit", "quantity": 3, "notes": ""},
        ],
        "current_index": 0,
        "item_results": [],
        "order_number": None,
        "screenshots": [],
        "error": None,
    }


def test_three_item_loop(sample_state):
    from app.graph.build import has_items

    assert has_items(sample_state) == "browse"

    for i in range(3):
        sample_state["current_index"] = i
        assert has_items(sample_state) == "browse"

    sample_state["current_index"] = 3
    assert has_items(sample_state) == "check_cart"


def test_all_skipped_path(sample_state):
    from app.graph.build import anything_in_cart

    sample_state["current_index"] = 3
    sample_state["item_results"] = [
        {"sku": "THERMAL-PASTE-001", "name": "Thermal Paste", "status": "skipped",
         "reasoning": "No match", "product_title": None, "unit_price": None, "quantity": 10},
        {"sku": "MECH-KEYB-003", "name": "Keyboard", "status": "skipped",
         "reasoning": "No match", "product_title": None, "unit_price": None, "quantity": 3},
        {"sku": "NO-MATCH-008", "name": "Connector Kit", "status": "skipped",
         "reasoning": "No match", "product_title": None, "unit_price": None, "quantity": 3},
    ]

    assert any(r["status"] == "matched" for r in sample_state["item_results"]) is False
    assert anything_in_cart(sample_state) == "empty"


def test_some_matched_path(sample_state):
    from app.graph.build import anything_in_cart

    sample_state["current_index"] = 3
    sample_state["item_results"] = [
        {"sku": "THERMAL-PASTE-001", "name": "Thermal Paste", "status": "matched",
         "reasoning": "Good match", "product_title": "ArcticBond TX-4", "unit_price": 8.99, "quantity": 10},
        {"sku": "NO-MATCH-008", "name": "Connector Kit", "status": "skipped",
         "reasoning": "No match", "product_title": None, "unit_price": None, "quantity": 3},
    ]

    assert anything_in_cart(sample_state) == "checkout"


def test_empty_plan_skips_all(sample_state):
    from app.graph.build import has_plan

    sample_state["plan"] = []
    assert has_plan(sample_state) == "empty"

    sample_state["plan"] = None
    assert has_plan(sample_state) == "empty"
