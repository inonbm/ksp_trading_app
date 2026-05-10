import os
import pytest
import uuid
from unittest.mock import patch
from services.trading_service import run_trading_flow
from services.checkout_service import run_checkout_flow
from domain.models import Product

SCREENSHOT_PATH = "proof_screenshot.png"


@pytest.mark.asyncio
async def test_full_automation_flow():
    """
    E2E test for the complete trading flow (Section 7):
    Phase 1: Search → Select Cheapest  (via /api/trade)
    Phase 2: Cart Checkout → Screenshot  (via /api/checkout)
    Uses mocks to avoid real network calls in CI.
    """
    if os.path.exists(SCREENSHOT_PATH):
        os.remove(SCREENSHOT_PATH)

    request_id = str(uuid.uuid4())

    mock_products = [
        Product(id="1", title="Mock אוזניות Pro",     price=299.0, currency="ILS",
                product_url="http://ksp.co.il/mock1", source="KSP",
                image_url="https://ksp.co.il/shop/items/111.jpg", specs="צבע: שחור"),
        Product(id="2", title="Mock אוזניות Basic",   price=89.0,  currency="ILS",
                product_url="http://ksp.co.il/mock2", source="KSP",
                image_url="https://ksp.co.il/shop/items/222.jpg"),
        Product(id="3", title="Mock אוזניות Premium", price=599.0, currency="ILS",
                product_url="http://ksp.co.il/mock3", source="KSP"),
    ]

    async def mock_search(query, max_results=10):
        return sorted(mock_products, key=lambda p: p.price)

    # ── Phase 1: Search ──────────────────────────────────────────────────────
    with patch('services.trading_service.search_products', side_effect=mock_search):
        result = await run_trading_flow(query="אוזניות", request_id=request_id)

        assert "products" in result, "Result must contain 'products' list"
        assert len(result["products"]) == 3

        # Products sorted cheapest → most expensive
        prices = [p["price"] for p in result["products"]]
        assert prices == sorted(prices), f"Must be sorted by price: {prices}"

        # Cheapest identified correctly
        assert result["selected_product"]["price"] == 89.0

        # Trace must contain only search steps (no checkout in search flow)
        step_names = [t["step"] for t in result["trace_details"]]
        assert "search_products"      in step_names
        assert "get_cheapest_product" in step_names
        assert "add_to_cart_and_checkout" not in step_names, \
            "Checkout must NOT be triggered automatically during search"

        for step in result["trace_details"]:
            assert step["status"] == "success"
            assert step["execution_time"] >= 0

    # ── Phase 2: Checkout ────────────────────────────────────────────────────
    async def mock_multi_checkout(products, user_details):
        with open(SCREENSHOT_PATH, "wb") as f:
            f.write(b"PNG_FAKE_PROOF")
        return SCREENSHOT_PATH

    with patch('services.checkout_service.add_multiple_to_cart_and_checkout',
               side_effect=mock_multi_checkout):
        checkout_result = await run_checkout_flow(
            products=[p.model_dump() for p in mock_products],
            user_details={"full_name": "ישראל ישראלי", "phone": "0501234567",
                          "email": "test@example.com", "city": "תל אביב", "street": "הרצל 1"},
            request_id=request_id
        )
        assert "screenshot_path" in checkout_result

    # Screenshot must exist after checkout
    assert os.path.exists(SCREENSHOT_PATH), "proof_screenshot.png must be created"
    assert os.path.getsize(SCREENSHOT_PATH) > 0,  "Screenshot must not be empty"
