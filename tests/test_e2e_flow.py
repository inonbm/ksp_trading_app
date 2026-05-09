import os
import pytest
import uuid
from unittest.mock import patch
from services.trading_service import run_trading_flow
from domain.models import Product

@pytest.mark.asyncio
async def test_full_automation_flow():
    """E2E test for the trading flow using mocks."""
    screenshot_path = "proof_screenshot.png"
    if os.path.exists(screenshot_path):
        os.remove(screenshot_path)

    request_id = str(uuid.uuid4())

    async def mock_search_products(query, max_results=10):
        return [
            Product(id="1", title=f"Mock {query}", price=50.0, currency="ILS",
                    product_url="http://ksp.co.il/mock", source="KSP",
                    image_url="https://img.ksp.co.il/mock.jpg", specs="אחסון: 128"),
            Product(id="2", title=f"Mock {query} Pro", price=100.0, currency="ILS",
                    product_url="http://ksp.co.il/mock2", source="KSP"),
        ]

    with patch('services.trading_service.search_products', side_effect=mock_search_products):
        result = await run_trading_flow(query="כבל USB", request_id=request_id)

        assert "products" in result
        assert len(result["products"]) == 2
        # Verify sorted by price (cheapest first)
        assert result["products"][0]["price"] <= result["products"][1]["price"]
        assert "trace_details" in result
        assert len(result["trace_details"]) > 0
