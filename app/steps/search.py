import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.sync_api import Page, expect

from app.settings import MOCKSHOP_URL


def search_product(page: Page, search_term: str) -> list[dict]:
    page.goto(MOCKSHOP_URL)
    page.fill("[data-testid='search-input']", search_term)
    page.click("[data-testid='search-submit']")
    expect(page).to_have_url(re.compile(r"/search\?q="))

    soup = BeautifulSoup(page.content(), "html.parser")
    cards = soup.select("[data-testid='result-card']")
    results = []
    for card in cards:
        title_el = card.select_one("[data-testid='result-title']")
        price_el = card.select_one("[data-testid='result-price']")
        if not title_el or not price_el:
            continue
        title = title_el.get_text(strip=True)
        href = title_el.get("href", "")
        price_text = price_el.get_text(strip=True)
        price_match = re.search(r"([\d.]+)", price_text)
        price = float(price_match.group(1)) if price_match else 0.0
        url = urljoin(MOCKSHOP_URL, href)
        results.append({"title": title, "price": price, "url": url})

    return results
