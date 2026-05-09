import uuid
import re
import os
import logging
from typing import List
from playwright.async_api import async_playwright

from domain.models import Product

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

MAX_RETRIES = 3


async def search_products(query: str, max_results: int = 5) -> List[Product]:
    """
    Searches for products on KSP using Playwright and returns a list of validated Product models.
    Implements retry/backoff for robustness (Section 4.2).
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = await _search_products_attempt(query, max_results)
            if result:
                return result
            logger.warning(f"Search attempt {attempt}/{MAX_RETRIES} returned 0 products.")
        except Exception as e:
            logger.warning(f"Search attempt {attempt}/{MAX_RETRIES} failed: {e}")
        if attempt < MAX_RETRIES:
            logger.info(f"Retrying in 2 seconds...")
    return []


async def _search_products_attempt(query: str, max_results: int) -> List[Product]:
    """
    Single attempt to search products. Separated for retry logic.
    """
    products: List[Product] = []

    async with async_playwright() as p:
        headless_mode = os.getenv("PLAYWRIGHT_HEADLESS", "False").lower() == "true"
        browser = await p.chromium.launch(
            headless=headless_mode,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            url = "https://ksp.co.il/"
            logger.info(f"[Attempt] Navigating to {url}")
            await page.goto(url, wait_until="domcontentloaded")

            # Dismiss any newsletter/ad/cookie popups
            await page.keyboard.press("Escape")

            # Locate search input with fallback strategy
            logger.info("Locating search input...")
            try:
                search_input = page.get_by_placeholder(re.compile(r"חפש|חיפוש|search", re.IGNORECASE)).first
                await search_input.wait_for(state="visible", timeout=8000)
            except Exception:
                logger.warning("Primary search locator failed. Trying fallback...")
                search_input = page.locator('input[type="search"], input[type="text"]').first
                await search_input.wait_for(state="visible", timeout=8000)

            # Click to focus, then type using page.keyboard to avoid stale locator
            await search_input.click()
            await page.keyboard.type(query, delay=50)
            logger.info(f"Typed query: {query}. Submitting...")
            await page.keyboard.press("Enter")

            # Wait for the search results page to fully load
            logger.info("Waiting for search results page...")
            await page.wait_for_load_state("domcontentloaded", timeout=15000)

            # Scroll down aggressively to trigger lazy-loaded product grid
            # KSP renders filters/brands first, product cards appear lower
            for scroll_step in range(4):
                await page.evaluate("window.scrollBy(0, 500)")
                logger.info(f"Scrolled down (step {scroll_step + 1}/4)")

            # Wait briefly for lazy-loaded content to render after scrolling
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass  # networkidle might not fire; that's ok

            # KSP uses CSS Modules: a[class*="productTitle"] targets only search result titles
            # This EXCLUDES promoted carousels, sliders, and banners which don't use this class
            product_title_selector = 'a[class*="productTitle"]'
            logger.info(f"Looking for product titles: {product_title_selector}")

            try:
                await page.wait_for_selector(product_title_selector, timeout=15000)
            except Exception:
                logger.error("Product title elements not found. The grid may not have loaded.")
                return products

            title_elements = page.locator(product_title_selector)
            count = await title_elements.count()
            logger.info(f"Found {count} product title elements in search grid.")

            for i in range(min(count, max_results)):
                try:
                    title_el = title_elements.nth(i)

                    # --- TITLE ---
                    title = (await title_el.inner_text()).strip()
                    if not title or len(title) < 3:
                        continue

                    # --- URL ---
                    href = await title_el.get_attribute("href")
                    if not href or "/web/item/" not in href:
                        continue
                    product_url = f"https://ksp.co.il{href}" if href.startswith("/") else href

                    # --- PRICE ---
                    # Walk up to the nearest ancestor that contains a ₪ price
                    price_float = await _extract_price_from_card(title_el, title)

                    if price_float == 0.0:
                        logger.warning(f"No price for '{title[:30]}'. Skipping.")
                        continue

                    product = Product(
                        id=str(uuid.uuid4()),
                        title=title,
                        price=price_float,
                        currency="ILS",
                        product_url=product_url,
                        source="KSP"
                    )
                    products.append(product)
                    logger.info(f"✓ {product.title[:50]} | {product.price} ₪")

                except Exception as ex:
                    logger.warning(f"Error on product #{i}: {ex}. Skipping.")
                    continue

        finally:
            logger.info("Closing browser.")
            await context.close()
            await browser.close()

    return products


async def _extract_price_from_card(title_el, title_text: str) -> float:
    """
    Extracts the product price by traversing up the DOM from the title element
    to find the containing card, then searching for ₪-formatted prices.
    Skips the title text line and Eilat price lines.
    """
    # Try progressively larger ancestor scopes
    for xpath_expr in [
        "xpath=ancestor::div[1]",      # immediate parent div
        "xpath=ancestor::div[2]",      # grandparent div
        "xpath=ancestor::div[3]",      # great-grandparent
    ]:
        try:
            ancestor = title_el.locator(xpath_expr)
            card_text = await ancestor.inner_text()

            price = _parse_price_from_text(card_text, title_text)
            if price > 0:
                return price
        except Exception:
            continue

    return 0.0


def _parse_price_from_text(text: str, title_to_skip: str) -> float:
    """
    Parses a price (float) from a block of text.
    Requires ₪ symbol to be present. Skips the title line and Eilat prices.
    """
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        # Skip the title line itself
        if line == title_to_skip:
            continue
        # Skip Eilat price lines
        if "אילת" in line:
            continue
        # Match: "1,234₪" or "₪1,234" or "1,234 ₪" or "₪ 1,234"
        match = re.search(r'([\d,]+(?:\.\d+)?)\s*₪|₪\s*([\d,]+(?:\.\d+)?)', line)
        if match:
            raw = (match.group(1) or match.group(2)).replace(",", "")
            try:
                price = float(raw)
                if price > 10:  # Valid product prices are > 10 ₪
                    return price
            except ValueError:
                continue
    return 0.0
