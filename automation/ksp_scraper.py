import uuid
import re
import logging
from typing import List
from playwright.async_api import async_playwright

# In order to import Product, we need to make sure python finds it in the domain package.
# Assuming this script is run from the project root or used as a module.
from domain.models import Product

# Configure basic logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

async def search_products(query: str, max_results: int = 5) -> List[Product]:
    """
    Searches for products on KSP using Playwright and returns a list of validated Product models.
    """
    products: List[Product] = []
    
    async with async_playwright() as p:
        # Launch browser in non-headless mode for debugging and bypassing basic bot protections
        import os
        headless_mode = os.getenv("PLAYWRIGHT_HEADLESS", "False").lower() == "true"
        browser = await p.chromium.launch(headless=headless_mode, args=["--disable-blink-features=AutomationControlled"])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            url = "https://ksp.co.il/"
            logger.info(f"Navigating to {url} to emulate human search")
            await page.goto(url, wait_until="domcontentloaded")
            
            logger.info("Dismissing any potential popups...")
            await page.keyboard.press("Escape")
            
            logger.info("Locating search input...")
            try:
                # Use get_by_placeholder with regex for Hebrew/English
                search_input = page.get_by_placeholder(re.compile(r"חפש|חיפוש|search", re.IGNORECASE)).first
                await search_input.wait_for(state="visible", timeout=8000)
            except Exception:
                logger.warning("Primary search locator failed. Trying fallback locator...")
                search_input = page.locator('input[type="search"], input[type="text"]').first
                await search_input.wait_for(state="visible", timeout=8000)
                
            await search_input.fill(query)
            await search_input.press("Enter")
            logger.info(f"Submitted search for: {query}")
            
            # Explicitly wait for the product grid/items to load.
            # Using a generalized selector that looks for links containing '/web/item/'
            item_selector = "a[href*='/web/item/']" 
            
            try:
                logger.info(f"Waiting for selector: {item_selector}")
                await page.wait_for_selector(item_selector, timeout=15000)
            except Exception as e:
                logger.error(f"Failed to find product elements within timeout: {e}")
                return products
                
            # Find all matching elements
            elements = await page.locator(item_selector).element_handles()
            logger.info(f"Found {len(elements)} potential product elements.")
            
            for element in elements:
                if len(products) >= max_results:
                    break
                    
                try:
                    # Extract product URL
                    href = await element.get_attribute("href")
                    if not href:
                        continue
                    
                    product_url = f"https://ksp.co.il{href}" if href.startswith('/') else href
                    
                    # Extract all text from the card to parse title and price resiliently
                    inner_text = await element.inner_text()
                    if not inner_text:
                        continue
                        
                    lines = [line.strip() for line in inner_text.split('\n') if line.strip()]
                    if not lines:
                        continue
                        
                    # Generalized extraction: assume title is the longest string or first line
                    title = lines[0] if len(lines[0]) > 5 else (lines[1] if len(lines) > 1 else "Unknown Title")
                    
                    # Generalized extraction: price is a number often accompanied by '₪' or simply the largest number
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
                        logger.warning(f"Could not extract a valid price for product at {product_url}. Skipping.")
                        continue
                        
                    # Map to the strict Pydantic model
                    product = Product(
                        id=str(uuid.uuid4()),
                        title=title,
                        price=price_float,
                        currency="ILS",
                        product_url=product_url,
                        source="KSP"
                    )
                    
                    products.append(product)
                    logger.info(f"Successfully mapped Product: {product.title[:30]}... | {product.price} ILS")
                    
                except Exception as ex:
                    logger.warning(f"Error extracting an individual product: {ex}. Skipping element.")
                    continue
                    
        finally:
            logger.info("Closing browser cleanly.")
            await context.close()
            await browser.close()
            
    return products
