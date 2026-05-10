import time
import json
import logging
from automation.ksp_scraper import search_products
from automation.checkout_automation import get_cheapest_product

# Use a specific logger for Observability outputs
logger = logging.getLogger("ObservabilityLogger")


def log_step(request_id: str, step_name: str, exec_time: float, error: str = None):
    """
    Outputs structured JSON logs for observability.
    Includes: requestId, step_name, execution_time, error_details.
    """
    log_data = {
        "requestId": request_id,
        "step_name": step_name,
        "execution_time": round(exec_time, 4),
        "error_details": error
    }
    logger.info(json.dumps(log_data))


async def run_trading_flow(query: str, request_id: str) -> dict:
    """
    Search-only flow for the storefront UI:
    1. Search products (scrape KSP)
    2. Identify the cheapest product

    NOTE: Add-to-cart and checkout are handled separately via /api/checkout
    when the user clicks "מעבר לרכישה" in the cart drawer.
    This keeps search fast (~4-6 seconds) and non-blocking.
    """
    trace_details = []

    # ── Step 1: Search Products ──────────────────────────────────────────────
    start_time = time.time()
    try:
        products = await search_products(query, max_results=10)
        exec_time = time.time() - start_time
        log_step(request_id, "search_products", exec_time)
        trace_details.append({"step": "search_products", "execution_time": exec_time, "status": "success"})
    except Exception as e:
        exec_time = time.time() - start_time
        log_step(request_id, "search_products", exec_time, str(e))
        trace_details.append({"step": "search_products", "execution_time": exec_time, "status": "failed"})
        raise e

    if not products:
        raise ValueError(f"לא נמצאו מוצרים עבור החיפוש: '{query}'")

    # ── Step 2: Identify Cheapest Product ────────────────────────────────────
    start_time = time.time()
    try:
        cheapest = await get_cheapest_product(products)
        exec_time = time.time() - start_time
        log_step(request_id, "get_cheapest_product", exec_time)
        trace_details.append({"step": "get_cheapest_product", "execution_time": exec_time, "status": "success"})
    except Exception as e:
        exec_time = time.time() - start_time
        log_step(request_id, "get_cheapest_product", exec_time, str(e))
        trace_details.append({"step": "get_cheapest_product", "execution_time": exec_time, "status": "failed"})
        raise e

    return {
        "products": [p.model_dump() for p in products],
        "selected_product": cheapest.model_dump(),
        "total_found": len(products),
        "order_status": "ממתין לאישור",
        "trace_details": trace_details
    }
