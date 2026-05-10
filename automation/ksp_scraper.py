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

                    # Image URL — target the specific product image wrapper
                    # KSP uses class "imageWrapperLink-*" for the product image container
                    image_url = await _extract_image_url(title_el)

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


def _normalize_image_url(url: str) -> str:
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
    # Reject common non-product image patterns
    reject_patterns = ["logo", "placeholder", "blank", "default", "sprite", "icon", "favicon"]
    url_lower = url.lower()
    return not any(p in url_lower for p in reject_patterns)


async def _extract_image_url(title_el) -> str:
    """
    Extracts the real product image URL from the product card.
    KSP uses CSS-module class 'imageWrapperLink-*' for the image container.
    Images may be lazy-loaded with data-src, srcset, or data-lazy attributes.
    """
    # Strategy 1: Find the sibling imageWrapperLink element in the product card
    try:
        # Go up to the product card container, then find the image wrapper
        for depth in range(1, 5):
            try:
                ancestor = title_el.locator(f"xpath=ancestor::div[{depth}]")
                img_wrapper = ancestor.locator('a[class*="imageWrapperLink"], div[class*="imageWrapper"]').first
                img = img_wrapper.locator("img").first
                
                # Try data-src first (lazy-loading), then srcset, then src
                for attr in ["data-src", "data-lazy", "data-original", "srcset"]:
                    val = await img.get_attribute(attr)
                    if val:
                        # srcset may contain multiple URLs; take the first/largest one
                        if attr == "srcset":
                            val = val.split(",")[0].strip().split(" ")[0]
                        url = _normalize_image_url(val)
                        if _is_valid_product_image(url):
                            return url

                # Fallback: use src if it's a real product image
                src = await img.get_attribute("src")
                url = _normalize_image_url(src)
                if _is_valid_product_image(url):
                    return url
            except Exception:
                continue
    except Exception:
        pass

    # Strategy 2: Find ANY img in a nearby sibling container with a product-like URL
    try:
        for depth in range(1, 4):
            ancestor = title_el.locator(f"xpath=ancestor::div[{depth}]")
            imgs = ancestor.locator("img")
            count = await imgs.count()
            for j in range(count):
                img = imgs.nth(j)
                for attr in ["data-src", "data-lazy", "src"]:
                    val = await img.get_attribute(attr)
                    url = _normalize_image_url(val)
                    if _is_valid_product_image(url) and ("img.ksp" in url or "/item/" in url or "/upload/" in url):
                        return url
    except Exception:
        pass

    return None

