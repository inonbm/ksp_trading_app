"""
Checkout Automation — Playwright multi-product cart + checkout flow.

KSP Cart Page Flow (from DOM inspection of proof_screenshot.png):
  1. Add each product to its product page → click "הוסף לעגלה"
  2. Navigate to /web/cart
  3. Select the "משלוח" (delivery) radio option
  4. Wait for the delivery form to expand
  5. Fill: full_name, phone, email, city, street
  6. Take proof screenshot
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
    """Single-product checkout — delegates to multi-product function."""
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
    Multi-product checkout flow with retry.
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
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/115.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900}
        )
        context.set_default_timeout(12000)
        page = await context.new_page()

        try:
            # ── Step 1: Add each product to the KSP cart ──────────────────────
            for i, product in enumerate(products):
                url   = product.get("product_url") or product.get("url", "")
                title = product.get("title", "מוצר")[:50]
                logger.info(f"[{i+1}/{len(products)}] → {url}")

                await page.goto(url, wait_until="domcontentloaded", timeout=12000)
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(300)

                added = await _click_add_to_cart(page)
                logger.info(f"  {'✓ Added' if added else '⚠ Failed to add'}: {title}")

                if i < len(products) - 1:
                    await page.wait_for_timeout(600)

            # ── Step 2: Navigate to cart ───────────────────────────────────────
            logger.info("Navigating to /web/cart ...")
            await page.goto("https://ksp.co.il/web/cart",
                            wait_until="domcontentloaded", timeout=12000)
            await page.wait_for_timeout(1200)

            # ── Step 3: Select "משלוח" (delivery) option ──────────────────────
            logger.info("Selecting delivery option (משלוח)...")
            await _select_delivery(page)

            # ── Step 4: Fill shipping form ─────────────────────────────────────
            logger.info("Filling shipping details...")
            await _fill_shipping_details(page, user_details)

            # ── Step 5: Take proof screenshot ─────────────────────────────────
            try:
                await page.wait_for_load_state("networkidle", timeout=3000)
            except Exception:
                pass
            await page.wait_for_timeout(800)

            screenshot_path = "proof_screenshot.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            logger.info(f"Screenshot saved: {screenshot_path}")
            return screenshot_path

        finally:
            await context.close()
            await browser.close()


async def _click_add_to_cart(page: Page) -> bool:
    """
    Clicks Add-to-Cart on a KSP product page.
    Strategy 1: button by ARIA role + Hebrew text.
    Strategy 2: JS force-click (bypasses MUI backdrop overlays).
    """
    add_regex = re.compile(
        r"הוספה לעגלה|הוסף לעגלה|לקניה|Add to cart", re.IGNORECASE
    )

    # Strategy 1 — Playwright locator
    try:
        btn = page.get_by_role("button", name=add_regex).first
        await btn.wait_for(state="visible", timeout=5000)
        await page.keyboard.press("Escape")   # dismiss any popup
        await page.wait_for_timeout(300)
        await btn.click()
        await page.wait_for_timeout(700)
        return True
    except Exception:
        pass

    # Strategy 2 — JS click (bypasses overlay z-index issues)
    try:
        ok = await page.evaluate("""
            () => {
                const btns = [...document.querySelectorAll('button')];
                const t = btns.find(b =>
                    /הוספה לעגלה|הוסף לעגלה|לקניה|add to cart/i.test(b.textContent));
                if (t) { t.click(); return true; }
                return false;
            }
        """)
        if ok:
            await page.wait_for_timeout(700)
            return True
    except Exception:
        pass

    return False


async def _select_delivery(page: Page) -> bool:
    """
    Clicks the "משלוח" (home delivery) shipping option on the KSP cart page.
    KSP renders the shipping methods as radio inputs or clickable cards.

    DOM pattern observed in screenshot:
      • Cards with text "אילת", "משלוח", "איסוף עצמי"
      • The delivery card must be clicked to open the address form below.
    """

    # Strategy 1: find a radio/button/label containing "משלוח" (but NOT "אילת")
    selectors_to_try = [
        # Card / label approach
        "label:has-text('משלוח')",
        "div[role='radio']:has-text('משלוח')",
        "button:has-text('משלוח')",
        # Input radio
        "input[type='radio'][value*='delivery']",
        "input[type='radio'][value*='ship']",
        "input[type='radio'][value*='משלוח']",
    ]

    for selector in selectors_to_try:
        try:
            els = page.locator(selector)
            count = await els.count()
            for idx in range(count):
                el = els.nth(idx)
                text = (await el.inner_text()).strip() if await el.count() else ""
                # Skip "אילת" shipping (Eilat-only)
                if "אילת" in text:
                    continue
                await el.click(timeout=3000)
                await page.wait_for_timeout(800)
                logger.info(f"  ✓ Clicked delivery option (selector: {selector})")
                return True
        except Exception:
            continue

    # Strategy 2: JS — find and click any element whose text is exactly "משלוח"
    try:
        clicked = await page.evaluate("""
            () => {
                const all = document.querySelectorAll('*');
                for (const el of all) {
                    const t = el.innerText?.trim();
                    if (t === 'משלוח' || t?.startsWith('משלוח')) {
                        el.click();
                        return true;
                    }
                }
                return false;
            }
        """)
        if clicked:
            await page.wait_for_timeout(800)
            logger.info("  ✓ Clicked delivery option via JS text search")
            return True
    except Exception:
        pass

    logger.warning("  ⚠ Could not find delivery option — form may not expand")
    return False


async def _fill_shipping_details(page: Page, user_details: Dict[str, str]) -> None:
    """
    Fills the visible shipping form on the KSP cart page.
    Waits briefly for the form to appear after the delivery option is selected,
    then fills each field using multiple selector strategies.
    """
    # Wait for the form to appear after selecting delivery
    await page.wait_for_timeout(1000)

    full_name = user_details.get("full_name", "")
    phone     = user_details.get("phone", "")
    email     = user_details.get("email", "")
    city      = user_details.get("city", "")
    street    = user_details.get("street", "")

    # Each entry: (value, list-of-placeholder-patterns, optional CSS selector fallback)
    field_map = [
        (full_name, ["שם מלא", "Full Name", "שם", "name"],      None),
        (phone,     ["טלפון", "Phone", "נייד", "mobile"],        None),
        (email,     ["אימייל", "email", "Mail", "דואר"],          "input[type='email']"),
        (city,      ["עיר", "City", "ישוב", "עיר/ישוב"],          None),
        (street,    ["רחוב", "Street", "כתובת", "רחוב ומספר"],   None),
    ]

    for value, placeholders, css_fallback in field_map:
        if not value:
            continue
        filled = False

        # Try each Hebrew/English placeholder pattern
        for ph in placeholders:
            try:
                field = page.get_by_placeholder(
                    re.compile(ph, re.IGNORECASE)
                ).first
                await field.wait_for(state="visible", timeout=2000)
                await field.triple_click()   # select all existing text first
                await field.fill(value)
                logger.info(f"  ✓ Filled '{ph}' = '{value}'")
                filled = True
                break
            except Exception:
                continue

        # CSS fallback (email field)
        if not filled and css_fallback:
            try:
                field = page.locator(css_fallback).first
                await field.wait_for(state="visible", timeout=2000)
                await field.triple_click()
                await field.fill(value)
                logger.info(f"  ✓ Filled (css: {css_fallback}) = '{value}'")
            except Exception:
                pass
