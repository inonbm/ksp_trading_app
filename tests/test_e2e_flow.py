import os
import pytest
import uuid
from unittest.mock import patch, AsyncMock
from services.trading_service import run_trading_flow
from domain.models import Product

SCREENSHOT_PATH = "proof_screenshot.png"


@pytest.mark.asyncio
async def test_full_automation_flow():
    """
    E2E test for the complete trading flow (Section 7):
    Search → Select Cheapest → Add to Cart → Screenshot proof.
    Uses mocks to avoid real network calls in CI.
    """
    # Clean up any leftover screenshot
    if os.path.exists(SCREENSHOT_PATH):
        os.remove(SCREENSHOT_PATH)

    request_id = str(uuid.uuid4())

    # Mock products with different prices to test selection logic
    mock_products = [
        Product(id="1", title="Mock אוזניות Pro", price=299.0, currency="ILS",
                product_url="http://ksp.co.il/mock1", source="KSP",
                image_url="https://ksp.co.il/shop/items/111.jpg", specs="צבע: שחור"),
        Product(id="2", title="Mock אוזניות Basic", price=89.0, currency="ILS",
                product_url="http://ksp.co.il/mock2", source="KSP",
                image_url="https://ksp.co.il/shop/items/222.jpg"),
        Product(id="3", title="Mock אוזניות Premium", price=599.0, currency="ILS",
                product_url="http://ksp.co.il/mock3", source="KSP"),
    ]

    async def mock_search(query, max_results=10):
        return sorted(mock_products, key=lambda p: p.price)

    # Mock checkout: creates a fake screenshot file (proof of execution)
    async def mock_checkout(product):
        with open(SCREENSHOT_PATH, "wb") as f:
            f.write(b"PNG_FAKE_PROOF")

    with patch('services.trading_service.search_products', side_effect=mock_search), \
         patch('services.trading_service.add_to_cart_and_checkout', side_effect=mock_checkout):

        result = await run_trading_flow(query="אוזניות", request_id=request_id)

        # ── Assert product list ──────────────────────────────────────────────
        assert "products" in result, "Result must contain 'products' list"
        assert len(result["products"]) == 3, "Should return all 3 products"

        # Must be sorted cheapest → most expensive
        prices = [p["price"] for p in result["products"]]
        assert prices == sorted(prices), f"Products must be sorted by price: {prices}"

        # ── Assert selected product ──────────────────────────────────────────
        assert "selected_product" in result, "Result must contain 'selected_product'"
        assert result["selected_product"]["price"] == 89.0, \
            f"Cheapest product (89₪) should be selected, got {result['selected_product']['price']}"

        # ── Assert trace ─────────────────────────────────────────────────────
        assert "trace_details" in result
        step_names = [t["step"] for t in result["trace_details"]]
        assert "search_products"          in step_names, "Trace must include search_products"
        assert "get_cheapest_product"     in step_names, "Trace must include get_cheapest_product"
        assert "add_to_cart_and_checkout" in step_names, "Trace must include add_to_cart_and_checkout"

        for step in result["trace_details"]:
            assert step["status"] == "success", f"Step {step['step']} should be success"
            assert step["execution_time"] >= 0

        # ── Assert proof screenshot ──────────────────────────────────────────
        assert os.path.exists(SCREENSHOT_PATH), \
            "proof_screenshot.png must be created after successful checkout"
        assert os.path.getsize(SCREENSHOT_PATH) > 0, "Screenshot file must not be empty"
