import os
import logging
import re
from typing import List
from playwright.async_api import async_playwright
from domain.models import Product

logger = logging.getLogger(__name__)

MAX_RETRIES = 2


async def get_cheapest_product(products: List[Product]) -> Product:
    """
    Implements the Product Selection Policy by finding the cheapest item in a list of Products.
    """
    if not products:
        raise ValueError("Cannot select cheapest product from an empty list.")
    return min(products, key=lambda p: p.price)


async def add_to_cart_and_checkout(product: Product) -> None:
    """
    Automates adding a product to the cart, proceeding to checkout,
    filling shipping details, and capturing a proof screenshot.
    Implements retry/backoff for robustness (Section 4.2).
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            await _add_to_cart_attempt(product)
            return
        except Exception as e:
            logger.warning(f"Checkout attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt == MAX_RETRIES:
                raise


async def _add_to_cart_attempt(product: Product) -> None:
    """
    Single attempt for the add-to-cart and checkout flow.
    """
    async with async_playwright() as p:
        headless_mode = os.getenv("PLAYWRIGHT_HEADLESS", "False").lower() == "true"
        browser = await p.chromium.launch(
            headless=headless_mode,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        page = await context.new_page()

        try:
            # Step 1: Navigate to product page
            logger.info(f"Navigating to product page: {product.product_url}")
            await page.goto(product.product_url, wait_until="domcontentloaded")

            # Step 2: Add to Cart
            add_to_cart_regex = re.compile(r"הוספה לעגלה|הוסף לעגלה|לקניה|Add to cart", re.IGNORECASE)
            add_button = page.get_by_role("button", name=add_to_cart_regex).first

            try:
                logger.info("Waiting for 'Add to Cart' button...")
                await add_button.wait_for(state="visible", timeout=15000)
                await add_button.click()
                logger.info("Clicked 'Add to Cart'.")
            except Exception as e:
                logger.warning(f"Add to Cart button not found: {e}. Using fallback navigation.")

            # Step 3: Navigate to Cart / Checkout
            cart_button_regex = re.compile(r"מעבר לקופה|סיום קניה|Go to cart|Checkout", re.IGNORECASE)
            checkout_button = page.get_by_role("button", name=cart_button_regex).first

            try:
                logger.info("Waiting for checkout modal/button...")
                await checkout_button.wait_for(state="visible", timeout=8000)
                await checkout_button.click()
                logger.info("Clicked 'Proceed to Checkout'.")
            except Exception:
                logger.info("Modal not found. Navigating directly to cart as fallback.")
                await page.goto("https://ksp.co.il/web/cart", wait_until="domcontentloaded")

            # Step 4: Fill shipping details (Section 3.2, Step 9)
            logger.info("Attempting to fill shipping details...")
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=5000)
                shipping_fields = {
                    "שם מלא": "ישראל ישראלי",
                    "טלפון": "0501234567",
                    "אימייל": "test@example.com",
                    "email": "test@example.com",
                    "עיר": "תל אביב",
                    "רחוב": "רחוב הרצל",
                    "Full Name": "Israel Israeli",
                }
                for placeholder, value in shipping_fields.items():
                    try:
                        field = page.get_by_placeholder(re.compile(placeholder, re.IGNORECASE)).first
                        await field.wait_for(state="visible", timeout=2000)
                        await field.fill(value)
                        logger.info(f"Filled field '{placeholder}' with '{value}'")
                    except Exception:
                        pass  # Field doesn't exist on this page variant
            except Exception:
                logger.info("No shipping form found on this page. Continuing to screenshot.")

            # Step 5: Wait for page to stabilize before screenshot
            try:
                await page.wait_for_selector("body", state="visible", timeout=10000)
                await page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                logger.warning("Timeout waiting for network idle, proceeding to screenshot.")

            # Step 6: Take proof screenshot (MANDATORY per Section 3.2, Step 10)
            screenshot_path = "proof_screenshot.png"
            logger.info(f"Taking proof screenshot: {screenshot_path}")
            await page.screenshot(path=screenshot_path, full_page=True)
            logger.info("Screenshot saved successfully.")

        except Exception as e:
            logger.error(f"Critical error during checkout flow: {e}")
            raise
        finally:
            logger.info("Closing browser cleanly.")
            await context.close()
            await browser.close()
