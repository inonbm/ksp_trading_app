import pytest
from pydantic import ValidationError
from domain.models import Product
from automation.checkout_automation import get_cheapest_product

def test_product_model_validation():
    # Test valid product
    p = Product(id="1", title="Test", price=100.5, currency="ILS", product_url="http://test.com", source="KSP")
    assert p.price == 100.5
    
    # Test valid product with string price that can be cast to float
    p2 = Product(id="2", title="Test2", price="200.5", currency="ILS", product_url="http://test.com", source="KSP")
    assert p2.price == 200.5
    
    # Test validation error on invalid price
    with pytest.raises(ValidationError):
        Product(id="3", title="Test3", price="invalid", currency="ILS", product_url="http://test.com", source="KSP")

    # Test validation error on negative price
    with pytest.raises(ValidationError):
        Product(id="4", title="Test4", price=-10.0, currency="ILS", product_url="http://test.com", source="KSP")

@pytest.mark.asyncio
async def test_get_cheapest_product():
    products = [
        Product(id="1", title="P1", price=100.0, currency="ILS", product_url="http://1", source="KSP"),
        Product(id="2", title="P2", price=50.0, currency="ILS", product_url="http://2", source="KSP"),
        Product(id="3", title="P3", price=200.0, currency="ILS", product_url="http://3", source="KSP")
    ]
    cheapest = await get_cheapest_product(products)
    assert cheapest.id == "2"
    assert cheapest.price == 50.0

@pytest.mark.asyncio
async def test_get_cheapest_product_empty_list():
    with pytest.raises(ValueError):
        await get_cheapest_product([])
