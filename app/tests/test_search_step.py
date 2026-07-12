import re
from unittest.mock import MagicMock, patch

import pytest
from playwright.sync_api import expect

from app.steps.search import search_product


@pytest.fixture
def mock_page():
    page = MagicMock()
    page.content.return_value = """
    <html>
    <body>
    <div data-testid="result-card">
        <a href="/product/1" data-testid="result-title">ArcticBond TX-4 Thermal Compound, 4 g</a>
        <div data-testid="result-price">$8.99</div>
    </div>
    <div data-testid="result-card">
        <a href="/product/2" data-testid="result-title">TX-4 Compound Spreader Kit</a>
        <div data-testid="result-price">$4.99</div>
    </div>
    </body>
    </html>
    """
    return page


def test_search_returns_parsed_results(mock_page):
    with patch("app.steps.search.MOCKSHOP_URL", "http://mockshop:8090"), patch("app.steps.search.expect"):
        results = search_product(mock_page, "thermal paste")

    assert len(results) == 2
    assert results[0]["title"] == "ArcticBond TX-4 Thermal Compound, 4 g"
    assert results[0]["price"] == 8.99
    assert "mockshop:8090/product/1" in results[0]["url"]
    assert results[1]["title"] == "TX-4 Compound Spreader Kit"
    assert results[1]["price"] == 4.99


def test_search_zero_results(mock_page):
    mock_page.content.return_value = """
    <html><body>
    <p>No products found.</p>
    </body></html>
    """
    with patch("app.steps.search.MOCKSHOP_URL", "http://mockshop:8090"), patch("app.steps.search.expect"):
        results = search_product(mock_page, "zzzzzzz")
    assert results == []


def test_search_navigates_and_submits(mock_page):
    with patch("app.steps.search.MOCKSHOP_URL", "http://mockshop:8090"), patch("app.steps.search.expect"):
        results = search_product(mock_page, "keyboard")

    mock_page.goto.assert_called_once_with("http://mockshop:8090")
    mock_page.fill.assert_called_once_with("[data-testid='search-input']", "keyboard")
    mock_page.click.assert_called_once_with("[data-testid='search-submit']")
