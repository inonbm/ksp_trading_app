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
            return await _search_products_attempt(query, max_results)
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

            # Wait for search results to load — look for product title links
            # KSP uses CSS-module classes like "productTitle-0-3-XXX"; match the stable prefix
            product_title_selector = 'a[class*="productTitle"]'
            try:
                logger.info(f"Waiting for product titles: {product_title_selector}")
                await page.wait_for_selector(product_title_selector, timeout=15000)
            except Exception as e:
                logger.error(f"Failed to find product title elements: {e}")
                return products

            # Scope extraction to the main content area, excluding sidebars/carousels
            # Each product card has a title link with class containing 'productTitle'
            title_elements = page.locator(product_title_selector)
            count = await title_elements.count()
            logger.info(f"Found {count} product title elements in search results.")

            for i in range(min(count, max_results)):
                try:
                    title_el = title_elements.nth(i)

                    # Extract title text
                    title = (await title_el.inner_text()).strip()
                    if not title or len(title) < 3:
                        continue

                    # Extract product URL from the title link's href
                    href = await title_el.get_attribute("href")
                    if not href or '/web/item/' not in href:
                        continue
                    product_url = f"https://ksp.co.il{href}" if href.startswith('/') else href

                    # Navigate UP to the product card container to find the price
                    # The card is the common ancestor containing both title and price
                    card = title_el.locator("xpath=ancestor::div[contains(@class, 'item')]").first

                    # Try to get the price from a dedicated price element within the card
                    price_float = 0.0
                    try:
                        # Get the full card text and extract price from lines containing ₪
                        card_text = await card.inner_text()
                        card_lines = [line.strip() for line in card_text.split('\n') if line.strip()]

                        for line in card_lines:
                            # Skip the title line itself to avoid extracting numbers from it
                            if line == title:
                                continue
                            # Skip Eilat price lines
                            if 'אילת' in line:
                                continue
                            # Look for price pattern: digits with optional commas, followed/preceded by ₪
                            price_match = re.search(r'([\d,]+(?:\.\d+)?)\s*₪|₪\s*([\d,]+(?:\.\d+)?)', line)
                            if price_match:
                                raw_price = (price_match.group(1) or price_match.group(2)).replace(',', '')
                                try:
                                    candidate = float(raw_price)
                                    if candidate > 10:  # Valid prices are > 10 ILS
                                        price_float = candidate
                                        break
                                except ValueError:
                                    continue
                    except Exception:
                        pass

                    # Fallback: if card-scoped extraction failed, try the sibling area
                    if price_float == 0.0:
                        try:
                            # Look for any element near the title with ₪ in its text
                            parent = title_el.locator("xpath=..")
                            parent_text = await parent.inner_text()
                            for line in parent_text.split('\n'):
                                line = line.strip()
                                if line == title or 'אילת' in line:
                                    continue
                                price_match = re.search(r'([\d,]+(?:\.\d+)?)\s*₪|₪\s*([\d,]+(?:\.\d+)?)', line)
                                if price_match:
                                    raw_price = (price_match.group(1) or price_match.group(2)).replace(',', '')
                                    candidate = float(raw_price)
                                    if candidate > 10:
                                        price_float = candidate
                                        break
                        except Exception:
                            pass

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
