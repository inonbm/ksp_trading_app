import logging
import asyncio
import re
from typing import List
from playwright.async_api import async_playwright
from domain.models import Product

logger = logging.getLogger(__name__)

async def get_cheapest_product(products: List[Product]) -> Product:
    """
    Implements the Product Selection Policy by finding the cheapest item in a list of Products.
    """
    if not products:
        raise ValueError("Cannot select cheapest product from an empty list.")
    
    # Sorts or directly finds the minimum based on the price field
    return min(products, key=lambda p: p.price)

async def add_to_cart_and_checkout(product: Product) -> None:
    """
    Automates adding a product to the cart, proceeding to checkout, and capturing a proof screenshot.
    """
    async with async_playwright() as p:
        # Launch browser in headed mode to pass bot checks and visually debug
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 720}
        )
        page = await context.new_page()
        
        try:
            logger.info(f"Navigating to product page: {product.product_url}")
            await page.goto(product.product_url, wait_until="domcontentloaded")
            
            # 1. Wait for and click 'Add to Cart'
            # We use a regex to match common Hebrew and English buttons for adding to cart
            add_to_cart_regex = re.compile(r"הוספה לעגלה|הוסף לעגלה|לקניה|Add to cart", re.IGNORECASE)
            add_button = page.get_by_role("button", name=add_to_cart_regex).first
            
            try:
                logger.info("Waiting for the 'Add to Cart' button...")
                await add_button.wait_for(state="visible", timeout=15000)
                await add_button.click()
                logger.info("Clicked 'Add to Cart'.")
            except Exception as e:
                logger.warning(f"Could not find or click typical Add to Cart button: {e}. Will attempt fallback navigation.")
                
            # 2. Handle Cart Popup / Navigate to Checkout
            # A modal usually appears allowing us to proceed to checkout
            cart_button_regex = re.compile(r"מעבר לקופה|סיום קניה|Go to cart|Checkout", re.IGNORECASE)
            checkout_button = page.get_by_role("button", name=cart_button_regex).first
            
            try:
                logger.info("Waiting for Cart confirmation popup/modal...")
                await checkout_button.wait_for(state="visible", timeout=8000)
                await checkout_button.click()
                logger.info("Clicked 'Proceed to Checkout' in modal.")
            except Exception:
                logger.info("Modal not found or clicked. Navigating directly to cart as a robust fallback.")
                await page.goto("https://ksp.co.il/web/cart", wait_until="domcontentloaded")
            
            # Wait for the checkout/cart page to fully render before screenshotting.
            # Avoids static sleep() by waiting for the network to idle so images load.
            try:
                await page.wait_for_selector("body", state="visible", timeout=10000)
                await page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                logger.warning("Timeout waiting for network idle, proceeding to screenshot anyway.")
            
            # 3. Take Proof Screenshot
            screenshot_path = "proof_screenshot.png"
            logger.info(f"Taking proof screenshot and saving to {screenshot_path}")
            await page.screenshot(path=screenshot_path, full_page=True)
            logger.info("Screenshot saved successfully.")
            
        except Exception as e:
            logger.error(f"A critical error occurred during the checkout flow: {e}")
            raise
        finally:
            logger.info("Closing browser cleanly.")
            await context.close()
            await browser.close()
