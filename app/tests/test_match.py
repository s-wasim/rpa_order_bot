from unittest.mock import MagicMock, patch

import pytest

from app.steps.match import match_product


class FakeMatchResult:
    """Simulates a Pydantic model output from with_structured_output."""

    def model_dump(self):
        return self._data

    def __init__(self, data):
        self._data = data


def test_match_returns_correct_index():
    llm = MagicMock()
    structured = MagicMock()
    llm.with_structured_output.return_value = structured
    structured.invoke.return_value = FakeMatchResult({
        "choice_index": 0,
        "confidence": 0.95,
        "reasoning": "Title matches directly.",
    })

    inventory_item = {"sku": "THERMAL-PASTE-001", "name": "Thermal Paste 4g Tube"}
    candidates = [
        {"title": "ArcticBond TX-4 Thermal Compound, 4 g", "price": 8.99, "url": "/product/1"},
    ]

    result = match_product(llm, inventory_item, candidates)
    assert result["choice_index"] == 0
    assert result["confidence"] > 0.9


def test_match_returns_null_for_no_match():
    llm = MagicMock()
    structured = MagicMock()
    llm.with_structured_output.return_value = structured
    structured.invoke.return_value = FakeMatchResult({
        "choice_index": None,
        "confidence": 0.0,
        "reasoning": "No product matches this inventory item on the storefront.",
    })

    inventory_item = {"sku": "NO-MATCH-008", "name": "Proprietary Connector Kit"}
    candidates = [
        {"title": "ArcticBond TX-4 Thermal Compound, 4 g", "price": 8.99, "url": "/product/1"},
    ]

    result = match_product(llm, inventory_item, candidates)
    assert result["choice_index"] is None


def test_reasoning_max_three_sentences():
    llm = MagicMock()
    structured = MagicMock()
    llm.with_structured_output.return_value = structured
    structured.invoke.return_value = FakeMatchResult({
        "choice_index": 0,
        "confidence": 0.85,
        "reasoning": "This is sentence one. This is sentence two. This is sentence three.",
    })

    inventory_item = {"sku": "MECH-KEYB-003", "name": "Mechanical Keyboard"}
    candidates = [
        {"title": "TypeMaster TKL Mechanical Keyboard, Cherry MX", "price": 89.99, "url": "/product/6"},
    ]

    result = match_product(llm, inventory_item, candidates)
    sentences = [s.strip() for s in result["reasoning"].split(".") if s.strip()]
    assert len(sentences) <= 3
