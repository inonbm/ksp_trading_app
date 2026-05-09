import time
import json
import logging
from automation.ksp_scraper import search_products
from automation.checkout_automation import get_cheapest_product, add_to_cart_and_checkout

# Use a specific logger for Observability outputs
logger = logging.getLogger("ObservabilityLogger")

def log_step(request_id: str, step_name: str, exec_time: float, error: str = None):
    """
    Helper function to strictly output structured JSON logs for observability.
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
    Orchestrates the Web Automation Trading flow.
    Returns the full sorted product list for the storefront display.
    """
    trace_details = []

    # Step 1: Search Products
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

    # Return the full sorted list for storefront display
    return {
        "products": [p.model_dump() for p in products],
        "total_found": len(products),
        "order_status": "Pending",
        "trace_details": trace_details
    }
