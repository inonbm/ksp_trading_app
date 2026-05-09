import uuid
import re
import os
import logging
from typing import List
from playwright.async_api import async_playwright

from domain.models import Product

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

MAX_RETRIES = 2


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
            if attempt == MAX_RETRIES:
                raise
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
            logger.info(f"[Attempt] Navigating to {url} to emulate human search")
            await page.goto(url, wait_until="domcontentloaded")

            # Dismiss any potential newsletter/ad/cookie popups
            logger.info("Dismissing any potential popups...")
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

            # Click to focus, use page.keyboard to avoid stale locator after auto-suggest
            await search_input.click()
            await page.keyboard.type(query, delay=50)
            logger.info(f"Typed query: {query}. Submitting search...")
            await page.keyboard.press("Enter")

            # Wait for the search results page to load
            # KSP search URL becomes /web/cat/search=... after Enter
            logger.info("Waiting for search results page to load...")
            await page.wait_for_load_state("domcontentloaded", timeout=15000)

            # KSP lazy-loads the product grid — scroll down to trigger rendering
            logger.info("Scrolling to trigger lazy-loaded product grid...")
            await page.evaluate("window.scrollBy(0, 600)")

            # Try multiple selectors — KSP uses CSS Modules with dynamic class suffixes
            # Priority 1: productTitle links (most precise)
            # Priority 2: generic item links (broader fallback)
            item_elements = None
            used_selector = ""

            for selector in ['a[class*="productTitle"]', 'a[href*="/web/item/"]']:
                try:
                    logger.info(f"Trying selector: {selector}")
                    await page.wait_for_selector(selector, timeout=15000)
                    count = await page.locator(selector).count()
                    if count > 0:
                        item_elements = page.locator(selector)
                        used_selector = selector
                        logger.info(f"Found {count} elements with selector: {selector}")
                        break
                except Exception:
                    logger.warning(f"Selector '{selector}' timed out. Trying next...")

            if not item_elements:
                logger.error("No product elements found with any selector.")
                return products

            count = await item_elements.count()

            for i in range(min(count, max_results)):
                try:
                    el = item_elements.nth(i)

                    # Extract href for product URL
                    href = await el.get_attribute("href")
                    if not href or "/web/item/" not in href:
                        continue
                    product_url = f"https://ksp.co.il{href}" if href.startswith("/") else href

                    # Extract title
                    if used_selector == 'a[class*="productTitle"]':
                        # Title is the text of the productTitle link itself
                        title = (await el.inner_text()).strip()
                    else:
                        # For generic links, extract text from the card
                        inner_text = await el.inner_text()
                        lines = [l.strip() for l in inner_text.split("\n") if l.strip()]
                        title = lines[0] if lines and len(lines[0]) > 3 else "Unknown"

                    if not title or len(title) < 3:
                        continue

                    # Extract price from the product card context
                    price_float = 0.0

                    # Walk up to the parent card container and extract price
                    try:
                        # Try the parent container (product card wraps title + price)
                        card = el.locator("xpath=ancestor::div[.//span[contains(text(),'₪')] or .//div[contains(text(),'₪')]]").first
                        card_text = await card.inner_text()
                    except Exception:
                        # Fallback: use the immediate parent
                        try:
                            parent = el.locator("xpath=../..")
                            card_text = await parent.inner_text()
                        except Exception:
                            continue

                    # Parse price from card text
                    for line in card_text.split("\n"):
                        line = line.strip()
                        # Skip the title line and Eilat price lines
                        if line == title or "אילת" in line:
                            continue
                        # Match price: number with optional commas + ₪ (in either order)
                        price_match = re.search(r'([\d,]+(?:\.\d+)?)\s*₪|₪\s*([\d,]+(?:\.\d+)?)', line)
                        if price_match:
                            raw = (price_match.group(1) or price_match.group(2)).replace(",", "")
                            try:
                                candidate = float(raw)
                                if candidate > 10:  # Valid prices > 10 ILS
                                    price_float = candidate
                                    break
                            except ValueError:
                                continue

                    if price_float == 0.0:
                        logger.warning(f"Could not extract price for '{title[:30]}'. Skipping.")
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
                    logger.info(f"Mapped: {product.title[:40]}... | {product.price} ILS")

                except Exception as ex:
                    logger.warning(f"Error extracting product #{i}: {ex}. Skipping.")
                    continue

        finally:
            logger.info("Closing browser cleanly.")
            await context.close()
            await browser.close()

    return products
