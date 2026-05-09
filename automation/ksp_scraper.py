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

            # Dismiss any potential newsletter/ad popups
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

            # Click to focus, then use page.keyboard to avoid stale locator after auto-suggest
            await search_input.click()
            await page.keyboard.type(query, delay=50)
            logger.info(f"Typed query: {query}. Submitting search...")
            await page.keyboard.press("Enter")

            # Wait for product grid to load
            item_selector = "a[href*='/web/item/']"
            try:
                logger.info(f"Waiting for product grid: {item_selector}")
                await page.wait_for_selector(item_selector, timeout=15000)
            except Exception as e:
                logger.error(f"Failed to find product elements within timeout: {e}")
                return products

            elements = await page.locator(item_selector).element_handles()
            logger.info(f"Found {len(elements)} potential product elements.")

            for element in elements:
                if len(products) >= max_results:
                    break

                try:
                    href = await element.get_attribute("href")
                    if not href:
                        continue

                    product_url = f"https://ksp.co.il{href}" if href.startswith('/') else href

                    inner_text = await element.inner_text()
                    if not inner_text:
                        continue

                    lines = [line.strip() for line in inner_text.split('\n') if line.strip()]
                    if not lines:
                        continue

                    title = lines[0] if len(lines[0]) > 5 else (lines[1] if len(lines) > 1 else "Unknown Title")

                    price_float = 0.0
                    for line in lines:
                        match = re.search(r'₪?\s*([\d,]+\.?\d*)', line)
                        if match:
                            price_str = match.group(1).replace(',', '')
                            try:
                                candidate_price = float(price_str)
                                if candidate_price > 0:
                                    price_float = candidate_price
                                    break
                            except ValueError:
                                continue

                    if price_float == 0.0:
                        logger.warning(f"Could not extract price for {product_url}. Skipping.")
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
                    logger.info(f"Mapped Product: {product.title[:30]}... | {product.price} ILS")

                except Exception as ex:
                    logger.warning(f"Error extracting product: {ex}. Skipping.")
                    continue

        finally:
            logger.info("Closing browser cleanly.")
            await context.close()
            await browser.close()

    return products
