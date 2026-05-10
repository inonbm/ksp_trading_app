import uuid
import re
import os
import logging
from typing import List, Optional
from playwright.async_api import async_playwright

from domain.models import Product

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

MAX_RETRIES = 2

# Spec patterns to extract from product titles
SPEC_PATTERNS = [
    (r'(\d+)\s*(?:GB|ג\'?יגה)', 'אחסון'),
    (r'(\d+)\s*(?:TB|טרה)', 'אחסון'),
    (r'(\d+)\s*(?:אינץ|אינטש|inch|")', 'גודל מסך'),
    (r'(שחור|לבן|אדום|כחול|ירוק|סגול|זהב|כסף|ורוד|אפור|Black|White|Red|Blue|Green|Purple|Gold|Silver|Pink|Gray|Grey)', 'צבע'),
]


def _extract_specs(title: str) -> Optional[str]:
    """Extract specifications like color, storage, and size from the product title."""
    specs = []
    for pattern, label in SPEC_PATTERNS:
        match = re.search(pattern, title, re.IGNORECASE)
        if match:
            specs.append(f"{label}: {match.group(1)}")
    return " | ".join(specs) if specs else None


async def search_products(query: str, max_results: int = 10) -> List[Product]:
    """
    Searches for products on KSP using Playwright. Returns sorted list.
    Only retries on hard failures (page crash/navigation error), NOT on empty results.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            result = await _search_products_attempt(query, max_results)
            # Sort and return immediately — don't retry if results are empty
            result.sort(key=lambda p: p.price)
            return result
        except Exception as e:
            logger.warning(f"Search attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt == MAX_RETRIES:
                raise
    return []


async def _search_products_attempt(query: str, max_results: int) -> List[Product]:
    """Single optimized attempt to search products."""
    products: List[Product] = []

    async with async_playwright() as p:
        # Default to headless=True for performance; only show browser when explicitly set to False
        headless_mode = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() != "false"
        browser = await p.chromium.launch(
            headless=headless_mode,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-images",       # Don't download images (we only need URLs)
                "--disable-extensions",
                "--no-sandbox",
            ]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        )
        # Set a global timeout of 10 seconds for all Playwright operations
        context.set_default_timeout(10000)
        page = await context.new_page()

        try:
            # Navigate to homepage
            logger.info(f"Navigating to ksp.co.il...")
            await page.goto("https://ksp.co.il/", wait_until="domcontentloaded", timeout=10000)
            await page.keyboard.press("Escape")

            # Locate search input — primary with 5s, fallback with 3s
            logger.info("Locating search input...")
            try:
                search_input = page.get_by_placeholder(re.compile(r"חפש|חיפוש|search", re.IGNORECASE)).first
                await search_input.wait_for(state="visible", timeout=5000)
            except Exception:
                search_input = page.locator('input[type="search"], input[type="text"]').first
                await search_input.wait_for(state="visible", timeout=3000)

            # Type fast — 20ms delay instead of 50ms
            await search_input.click()
            await page.keyboard.type(query, delay=20)
            await page.keyboard.press("Enter")

            # Wait for results page to load
            await page.wait_for_load_state("domcontentloaded", timeout=8000)

            # Single rapid scroll to trigger lazy grid
            await page.evaluate("window.scrollBy(0, 1500)")

            # Wait for product titles — 10s max
            product_title_selector = 'a[class*="productTitle"]'
            try:
                await page.wait_for_selector(product_title_selector, timeout=10000)
            except Exception:
                logger.info("No product titles found. Returning empty results.")
                return products

            title_elements = page.locator(product_title_selector)
            count = await title_elements.count()
            logger.info(f"Found {count} product titles.")

            # Extract products — batch all attribute reads per product for speed
            for i in range(min(count, max_results)):
                try:
                    title_el = title_elements.nth(i)

                    # Parallel-ish: get title + href in quick succession
                    title = (await title_el.inner_text()).strip()
                    if not title or len(title) < 3:
                        continue

                    href = await title_el.get_attribute("href")
                    if not href or "/web/item/" not in href:
                        continue
                    product_url = f"https://ksp.co.il{href}" if href.startswith("/") else href

                    # Price — fast extraction with 2-level ancestor check
                    price_float = await _extract_price_fast(title_el, title)
                    if price_float == 0.0:
                        continue

                    # Image — fast extraction, single pass
                    image_url = await _extract_image_fast(title_el)

                    # Specs — pure CPU, no DOM calls
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


async def _extract_price_fast(title_el, title_text: str) -> float:
    """Fast price extraction — only checks 2 ancestor levels."""
    for depth in [2, 3]:
        try:
            ancestor = title_el.locator(f"xpath=ancestor::div[{depth}]")
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


async def _extract_image_fast(title_el) -> Optional[str]:
    """
    Fast image extraction — single pass.
    Targets imageWrapperLink in ancestor, checks src only (no data-src loops).
    """
    try:
        ancestor = title_el.locator("xpath=ancestor::div[3]")
        img_wrapper = ancestor.locator('a[class*="imageWrapperLink"], div[class*="imageWrapper"]').first
        img = img_wrapper.locator("img").first
        src = await img.get_attribute("src")
        url = _normalize_image_url(src)
        if _is_valid_product_image(url):
            return url
    except Exception:
        pass

    # Quick fallback: any img in grandparent with product URL pattern
    try:
        ancestor = title_el.locator("xpath=ancestor::div[3]")
        img = ancestor.locator("img").first
        src = await img.get_attribute("src")
        url = _normalize_image_url(src)
        if _is_valid_product_image(url):
            return url
    except Exception:
        pass

    return None


def _normalize_image_url(url: str) -> Optional[str]:
    """Normalize a relative or protocol-relative URL to an absolute HTTPS URL."""
    if not url:
        return None
    url = url.strip()
    if url.startswith("//"):
        return f"https:{url}"
    if url.startswith("/"):
        return f"https://ksp.co.il{url}"
    return url


def _is_valid_product_image(url: str) -> bool:
    """Check that the URL is an actual product image, not a logo or placeholder."""
    if not url:
        return False
    reject = ["logo", "placeholder", "blank", "default", "sprite", "icon", "favicon"]
    url_lower = url.lower()
    return not any(p in url_lower for p in reject)
