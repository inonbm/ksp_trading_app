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

# Spec patterns to extract from product titles
SPEC_PATTERNS = [
    (r'(\d+)\s*(?:GB|ג\'?יגה)', 'אחסון'),
    (r'(\d+)\s*(?:TB|טרה)', 'אחסון'),
    (r'(\d+)\s*(?:אינץ|אינטש|inch|")', 'גודל מסך'),
    (r'(שחור|לבן|אדום|כחול|ירוק|סגול|זהב|כסף|ורוד|אפור|Black|White|Red|Blue|Green|Purple|Gold|Silver|Pink|Gray|Grey)', 'צבע'),
]


def _extract_specs(title: str) -> str:
    """Extract specifications like color, storage, and size from the product title."""
    specs = []
    for pattern, label in SPEC_PATTERNS:
        match = re.search(pattern, title, re.IGNORECASE)
        if match:
            specs.append(f"{label}: {match.group(1)}")
    return " | ".join(specs) if specs else None


async def search_products(query: str, max_results: int = 10) -> List[Product]:
    """
    Searches for products on KSP using Playwright and returns a sorted list of Product models.
    Implements retry/backoff for robustness (Section 4.2).
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = await _search_products_attempt(query, max_results)
            if result:
                # Sort from cheapest to most expensive
                result.sort(key=lambda p: p.price)
                return result
            logger.warning(f"Search attempt {attempt}/{MAX_RETRIES} returned 0 products.")
        except Exception as e:
            logger.warning(f"Search attempt {attempt}/{MAX_RETRIES} failed: {e}")
        if attempt < MAX_RETRIES:
            logger.info("Retrying...")
    return []


async def _search_products_attempt(query: str, max_results: int) -> List[Product]:
    """Single attempt to search products."""
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

            await page.keyboard.press("Escape")

            # Locate search input
            logger.info("Locating search input...")
            try:
                search_input = page.get_by_placeholder(re.compile(r"חפש|חיפוש|search", re.IGNORECASE)).first
                await search_input.wait_for(state="visible", timeout=8000)
            except Exception:
                search_input = page.locator('input[type="search"], input[type="text"]').first
                await search_input.wait_for(state="visible", timeout=8000)

            await search_input.click()
            await page.keyboard.type(query, delay=50)
            await page.keyboard.press("Enter")

            # Wait for search results page
            await page.wait_for_load_state("domcontentloaded", timeout=15000)

            # Scroll to trigger lazy-loaded product grid
            for i in range(4):
                await page.evaluate("window.scrollBy(0, 500)")

            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass

            # Find product title links — scoped to search results only
            product_title_selector = 'a[class*="productTitle"]'
            try:
                await page.wait_for_selector(product_title_selector, timeout=15000)
            except Exception:
                logger.error("Product title elements not found.")
                return products

            title_elements = page.locator(product_title_selector)
            count = await title_elements.count()
            logger.info(f"Found {count} product title elements.")

            for i in range(min(count, max_results)):
                try:
                    title_el = title_elements.nth(i)

                    # Title
                    title = (await title_el.inner_text()).strip()
                    if not title or len(title) < 3:
                        continue

                    # URL
                    href = await title_el.get_attribute("href")
                    if not href or "/web/item/" not in href:
                        continue
                    product_url = f"https://ksp.co.il{href}" if href.startswith("/") else href

                    # Image URL — find nearby img element in the product card
                    image_url = None
                    try:
                        card = title_el.locator("xpath=ancestor::div[.//img]").first
                        img = card.locator("img").first
                        image_url = await img.get_attribute("src")
                        if image_url and image_url.startswith("//"):
                            image_url = f"https:{image_url}"
                    except Exception:
                        pass

                    # Price
                    price_float = await _extract_price_from_card(title_el, title)
                    if price_float == 0.0:
                        continue

                    # Specs
                    specs = _extract_specs(title)

                    product = Product(
                        id=str(uuid.uuid4()),
                        title=title,
                        price=price_float,
                        currency="ILS",
                        product_url=product_url,
                        source="KSP",
                        image_url=image_url,
                        specs=specs,
                    )
                    products.append(product)
                    logger.info(f"✓ {product.title[:50]} | {product.price} ₪")

                except Exception as ex:
                    logger.warning(f"Error on product #{i}: {ex}. Skipping.")
                    continue

        finally:
            await context.close()
            await browser.close()

    return products


async def _extract_price_from_card(title_el, title_text: str) -> float:
    """Extract product price by traversing ancestors."""
    for xpath_expr in [
        "xpath=ancestor::div[1]",
        "xpath=ancestor::div[2]",
        "xpath=ancestor::div[3]",
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
    """Parse a price from text requiring ₪ symbol. Skips title and Eilat prices."""
    for line in text.split("\n"):
        line = line.strip()
        if not line or line == title_to_skip or "אילת" in line:
            continue
        match = re.search(r'([\d,]+(?:\.\d+)?)\s*₪|₪\s*([\d,]+(?:\.\d+)?)', line)
        if match:
            raw = (match.group(1) or match.group(2)).replace(",", "")
            try:
                price = float(raw)
                if price > 10:
                    return price
            except ValueError:
                continue
    return 0.0
