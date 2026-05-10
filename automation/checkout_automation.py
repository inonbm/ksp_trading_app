"""
Checkout Automation — Playwright multi-product cart + checkout flow.

Steps:
1. Open first product page → Add to cart
2. For each additional product → navigate to its page → Add to cart
3. Navigate to /web/cart
4. Fill shipping details
5. Capture proof screenshot
"""
import os
import re
import logging
from typing import List, Dict, Any
from playwright.async_api import async_playwright, Page
from domain.models import Product

logger = logging.getLogger(__name__)

MAX_RETRIES = 2


async def get_cheapest_product(products: List[Product]) -> Product:
    """Implements the Product Selection Policy — cheapest item wins."""
    if not products:
        raise ValueError("Cannot select cheapest product from an empty list.")
    return min(products, key=lambda p: p.price)


async def add_to_cart_and_checkout(product: Product) -> None:
    """
    Single-product checkout (used by the legacy trading_service flow).
    Delegates to the multi-product function with one item.
    """
    await add_multiple_to_cart_and_checkout(
        products=[product.model_dump()],
        user_details={
            "full_name": "ישראל ישראלי",
            "phone": "0501234567",
            "email": "test@example.com",
            "city": "תל אביב",
            "street": "הרצל 1",
        }
    )


async def add_multiple_to_cart_and_checkout(
    products: List[Dict[str, Any]],
    user_details: Dict[str, str]
) -> str:
    """
    Multi-product Playwright flow:
    1. Navigate to each product page → click "Add to Cart"
    2. Navigate to KSP cart (/web/cart)
    3. Fill shipping details with user_details
    4. Take proof screenshot → return path
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return await _checkout_attempt(products, user_details)
        except Exception as e:
            logger.warning(f"Checkout attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt == MAX_RETRIES:
                raise
    return "proof_screenshot.png"


async def _checkout_attempt(
    products: List[Dict[str, Any]],
    user_details: Dict[str, str]
) -> str:
    headless = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() != "false"

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        context.set_default_timeout(15000)
        page = await context.new_page()

        try:
            # ── Step 1: Add each product to cart ──────────────────────────────
            for i, product in enumerate(products):
                url = product.get("product_url") or product.get("url")
                title = product.get("title", "מוצר")[:40]
                logger.info(f"[{i+1}/{len(products)}] Navigating to: {url}")

                await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                await page.keyboard.press("Escape")

                added = await _click_add_to_cart(page)
                if added:
                    logger.info(f"  ✓ Added to cart: {title}")
                else:
                    logger.warning(f"  ⚠ Could not add: {title} — continuing.")

                # Small pause between products to avoid detection
                if i < len(products) - 1:
                    await page.wait_for_timeout(800)

            # ── Step 2: Navigate to KSP cart ──────────────────────────────────
            logger.info("Navigating to /web/cart...")
            await page.goto("https://ksp.co.il/web/cart", wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(1500)

            # ── Step 3: Fill shipping details ─────────────────────────────────
            logger.info("Filling shipping details...")
            await _fill_shipping_details(page, user_details)

            # ── Step 4: Screenshot ────────────────────────────────────────────
            try:
                await page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass

            screenshot_path = "proof_screenshot.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            logger.info(f"Screenshot saved: {screenshot_path}")
            return screenshot_path

        finally:
            await context.close()
            await browser.close()


async def _click_add_to_cart(page: Page) -> bool:
    """
    Tries multiple strategies to click the Add-to-Cart button on a KSP product page.
    Returns True if succeeded, False if not found.
    """
    add_regex = re.compile(r"הוספה לעגלה|הוסף לעגלה|לקניה|Add to cart", re.IGNORECASE)

    # Strategy 1: button by text role
    try:
        btn = page.get_by_role("button", name=add_regex).first
        await btn.wait_for(state="visible", timeout=6000)
        # Dismiss any backdrop/modal
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(400)
        await btn.click()
        await page.wait_for_timeout(800)
        return True
    except Exception:
        pass

    # Strategy 2: force-click via JS (bypasses overlay interception)
    try:
        added = await page.evaluate("""
            () => {
                const btns = [...document.querySelectorAll('button')];
                const target = btns.find(b =>
                    /הוספה לעגלה|הוסף לעגלה|לקניה|add to cart/i.test(b.textContent));
                if (target) { target.click(); return true; }
                return false;
            }
        """)
        if added:
            await page.wait_for_timeout(800)
            return True
    except Exception:
        pass

    return False


async def _fill_shipping_details(page: Page, user_details: Dict[str, str]) -> None:
    """
    Tries to fill visible form fields on the KSP checkout/cart page.
    Gracefully skips fields that don't exist on the current page variant.
    """
    field_map = [
        (user_details.get("full_name", ""), ["שם מלא", "Full Name", "שם"]),
        (user_details.get("phone", ""),     ["טלפון", "Phone", "נייד", "מספר טלפון"]),
        (user_details.get("email", ""),     ["אימייל", "email", "Email", "דוא.ל"]),
        (user_details.get("city", ""),      ["עיר", "City", "ישוב"]),
        (user_details.get("street", ""),    ["רחוב", "Street", "כתובת"]),
    ]

    for value, placeholders in field_map:
        if not value:
            continue
        for placeholder in placeholders:
            try:
                field = page.get_by_placeholder(re.compile(placeholder, re.IGNORECASE)).first
                await field.wait_for(state="visible", timeout=2000)
                await field.fill(value)
                logger.info(f"  Filled '{placeholder}' = '{value}'")
                break
            except Exception:
                continue
