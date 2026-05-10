"""
Checkout Service — Orchestrates multi-product cart checkout via Playwright.

Flow:
1. For each product URL → navigate → add to KSP cart
2. Navigate to KSP cart page
3. Fill shipping details (auto-fill)
4. Capture proof screenshot
"""
import time
import json
import logging
from typing import List, Dict, Any
from automation.checkout_automation import add_multiple_to_cart_and_checkout

logger = logging.getLogger("CheckoutService")


def log_step(request_id: str, step: str, exec_time: float, error: str = None):
    logger.info(json.dumps({
        "requestId": request_id,
        "step_name": step,
        "execution_time": round(exec_time, 4),
        "error_details": error
    }))


async def run_checkout_flow(
    products: List[Dict[str, Any]],
    user_details: Dict[str, str],
    request_id: str
) -> dict:
    """
    Runs the multi-product cart + checkout Playwright automation.
    """
    logger.info(f"[{request_id}] Starting checkout for {len(products)} products.")

    start = time.time()
    try:
        screenshot_path = await add_multiple_to_cart_and_checkout(products, user_details)
        exec_time = time.time() - start
        log_step(request_id, "checkout_flow", exec_time)
        logger.info(f"[{request_id}] Checkout completed in {exec_time:.2f}s. Screenshot: {screenshot_path}")
        return {"screenshot_path": screenshot_path}

    except Exception as e:
        exec_time = time.time() - start
        log_step(request_id, "checkout_flow", exec_time, str(e))
        logger.error(f"[{request_id}] Checkout failed: {e}")
        raise
