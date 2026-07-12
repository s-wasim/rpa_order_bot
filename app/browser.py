import logging
import os
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright, Page, BrowserContext

from . import settings

logger = logging.getLogger("rpa.browser")


def _origin_guard(route):
    request_url = route.request.url
    parsed = urlparse(request_url)
    allowed_host = urlparse(settings.MOCKSHOP_URL).hostname

    if parsed.hostname and parsed.hostname != allowed_host:
        logger.warning("Origin guard blocked request to %s (allowed host: %s)", request_url, allowed_host)
        # "blockedbyclient" is a valid Playwright abort error code.
        route.abort("blockedbyclient")
    else:
        route.continue_()


def create_context(headless=True):
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(headless=headless)
    context = browser.new_context()
    page = context.pages[0] if context.pages else context.new_page()
    page.route("**/*", _origin_guard)
    return context


def take_screenshot(page: Page, run_id, seq, label) -> str:
    screenshot_dir = Path(settings.DATA_DIR) / "screenshots" / str(run_id)
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{seq:03d}_{label}.png"
    filepath = str(screenshot_dir / filename)
    page.screenshot(path=filepath)
    return filepath


def close_context(context: BrowserContext):
    try:
        if context:
            browser = context.browser
            context.close()
            if browser:
                browser.close()
    except Exception:
        pass
