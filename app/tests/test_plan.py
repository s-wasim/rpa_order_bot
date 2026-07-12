from unittest.mock import MagicMock, patch

import pytest

from app.graph.nodes.plan import plan_node
from app.graph.state import OrderState


class FakePlan:
    def __init__(self, items):
        self.items = items


def test_plan_covers_all_low_stock():
    state: OrderState = {
        "run_id": 1,
        "low_stock": [
            {"sku": "THERMAL-PASTE-001", "name": "Thermal Paste 4g Tube",
             "qty": 2, "reorder_threshold": 5, "reorder_qty": 10, "on_order": 0},
            {"sku": "MECH-KEYB-003", "name": "Mechanical Keyboard",
             "qty": 1, "reorder_threshold": 3, "reorder_qty": 3, "on_order": 0},
            {"sku": "NO-MATCH-008", "name": "Proprietary Connector Kit",
             "qty": 1, "reorder_threshold": 3, "reorder_qty": 3, "on_order": 0},
        ],
        "plan": None,
        "current_index": 0,
        "item_results": [],
        "order_number": None,
        "screenshots": [],
        "error": None,
    }

    fake_plan_items = []
    for item in state["low_stock"]:
        fake_item = MagicMock()
        fake_item.sku = item["sku"]
        fake_item.name = item["name"]
        fake_item.search_terms = item["name"]
        fake_item.quantity = item["reorder_qty"]
        fake_item.notes = ""
        fake_plan_items.append(fake_item)

    with patch("app.graph.nodes.plan.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_structured = MagicMock()
        mock_llm.with_structured_output.return_value = mock_structured
        mock_structured.invoke.return_value = FakePlan(fake_plan_items)
        mock_get_llm.return_value = mock_llm

        with patch("app.graph.nodes.plan.get_session") as mock_session:
            mock_session.return_value.__enter__.return_value = MagicMock()
            result = plan_node(state)

    assert result["plan"] is not None
    assert len(result["plan"]) == 3
    assert result["plan"][0]["sku"] == "THERMAL-PASTE-001"
    assert result["plan"][1]["sku"] == "MECH-KEYB-003"
    assert result["plan"][2]["sku"] == "NO-MATCH-008"

    skus = {p["sku"] for p in result["plan"]}
    for item in state["low_stock"]:
        assert item["sku"] in skus
