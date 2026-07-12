from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from app.browser import _origin_guard, create_context, close_context, take_screenshot


@pytest.fixture
def mock_route():
    route = MagicMock()
    route.request.url = "http://evil.com/malware"
    return route


def test_origin_guard_blocks_external(mock_route):
    with patch("app.browser.settings.MOCKSHOP_URL", "http://mockshop:8090"):
        _origin_guard(mock_route)
    mock_route.abort.assert_called_once_with("blockedbyclient")


def test_origin_guard_passes_mockshop(mock_route):
    mock_route.request.url = "http://mockshop:8090/static/style.css"
    with patch("app.browser.settings.MOCKSHOP_URL", "http://mockshop:8090"):
        _origin_guard(mock_route)
    mock_route.continue_.assert_called_once()


def test_screenshot_creates_file(tmp_path, monkeypatch):
    mock_page = MagicMock()
    monkeypatch.setattr("app.browser.settings.DATA_DIR", str(tmp_path))
    result = take_screenshot(mock_page, 1, 1, "test-step")
    assert "001_test-step.png" in result
    assert str(tmp_path) in result
    mock_page.screenshot.assert_called_once_with(path=result)

    screenshot_path = tmp_path / "screenshots" / "1" / "001_test-step.png"
    assert screenshot_path.parent.exists()


@patch("app.browser.sync_playwright")
def test_context_creation(mock_sync_playwright):
    mock_playwright = MagicMock()
    mock_browser = MagicMock()
    mock_context = MagicMock()
    mock_page = MagicMock()

    mock_sync_playwright.return_value.start.return_value = mock_playwright
    mock_playwright.chromium.launch.return_value = mock_browser
    mock_browser.new_context.return_value = mock_context
    mock_context.pages = [mock_page]

    with patch("app.browser.settings.MOCKSHOP_URL", "http://mockshop:8090"):
        context = create_context(headless=True)

    mock_playwright.chromium.launch.assert_called_once_with(headless=True)
    assert context == mock_context
    mock_page.route.assert_called_once_with("**/*", _origin_guard)
