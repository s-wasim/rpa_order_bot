from unittest.mock import MagicMock, patch

import pytest

from app.scripted_run import run_scripted


@pytest.fixture
def mock_db():
    fake_inv = [
        MagicMock(
            sku="THERMAL-PASTE-001",
            name="Thermal Paste 4g Tube",
            qty=2,
            reorder_threshold=5,
            reorder_qty=10,
            on_order=0,
        ),
    ]

    with patch("app.scripted_run.get_session") as mock_get_session:
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session

        query_chain = MagicMock()
        query_chain.filter.return_value.all.return_value = fake_inv
        mock_session.query.return_value = query_chain

        yield mock_get_session


@patch("app.scripted_run.create_context")
@patch("app.scripted_run.search_product")
@patch("app.scripted_run.match_product")
@patch("app.scripted_run.add_to_cart")
@patch("app.scripted_run.checkout")
def test_scripted_run_full_flow(
    mock_checkout, mock_add_cart, mock_match, mock_search, mock_create_context,
    mock_db,
):
    mock_context = MagicMock()
    mock_page = MagicMock()
    mock_create_context.return_value = mock_context
    mock_context.pages = [mock_page]

    mock_search.return_value = [
        {"title": "ArcticBond TX-4 Thermal Compound, 4 g", "price": 8.99, "url": "/product/1"},
    ]
    mock_match.return_value = {"choice_index": 0, "confidence": 0.95, "reasoning": "Good match"}
    mock_add_cart.return_value = {"success": True, "cart_items": [{"title": "ArcticBond TX-4", "qty": 10}]}
    mock_checkout.return_value = "DM-12345"

    result = run_scripted(1)

    assert result["status"] == "succeeded"
    assert result["ordered"] == 1
    assert result["order_number"] == "DM-12345"

    mock_create_context.assert_called_once()
    mock_search.assert_called_once()
    mock_match.assert_called_once()
    mock_add_cart.assert_called_once()
    mock_checkout.assert_called_once()


@patch("app.scripted_run.create_context")
@patch("app.scripted_run.search_product")
def test_scripted_run_no_results(mock_search, mock_create_context, mock_db):
    mock_context = MagicMock()
    mock_page = MagicMock()
    mock_create_context.return_value = mock_context
    mock_context.pages = [mock_page]

    mock_search.return_value = []

    result = run_scripted(1)

    assert result["status"] == "succeeded"
    assert result["ordered"] == 0
    assert result["skipped"] == 1
