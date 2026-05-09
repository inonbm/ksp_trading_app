import pytest
from pydantic import ValidationError
from domain.models import Product, Cart
from automation.checkout_automation import get_cheapest_product


def test_product_model_validation():
    """Test that the Product Pydantic model normalizes data correctly."""
    # Valid product
    p = Product(id="1", title="Test", price=100.5, currency="ILS", product_url="http://test.com", source="KSP")
    assert p.price == 100.5

    # String price is coerced to float
    p2 = Product(id="2", title="Test2", price="200.5", currency="ILS", product_url="http://test.com", source="KSP")
    assert p2.price == 200.5

    # Invalid price string raises ValidationError
    with pytest.raises(ValidationError):
        Product(id="3", title="Test3", price="invalid", currency="ILS", product_url="http://test.com", source="KSP")

    # Negative price raises ValidationError (ge=0 constraint)
    with pytest.raises(ValidationError):
        Product(id="4", title="Test4", price=-10.0, currency="ILS", product_url="http://test.com", source="KSP")


def test_product_currency_normalization():
    """Test that currency field is stored correctly."""
    p = Product(id="1", title="Test", price=100.0, currency="ILS", product_url="http://test.com", source="KSP")
    assert p.currency == "ILS"


@pytest.mark.asyncio
async def test_get_cheapest_product():
    """Test product selection policy: must return the cheapest product."""
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
    """Test that an empty product list raises ValueError."""
    with pytest.raises(ValueError):
        await get_cheapest_product([])


def test_cart_total_price():
    """Test Cart.total_price computed property (Section 5 requirement)."""
    cart = Cart(items=[
        Product(id="1", title="P1", price=100.0, currency="ILS", product_url="http://1", source="KSP"),
        Product(id="2", title="P2", price=50.0, currency="ILS", product_url="http://2", source="KSP"),
    ])
    assert cart.total_price == 150.0


def test_cart_empty():
    """Test that an empty cart has a total_price of 0."""
    cart = Cart()
    assert cart.total_price == 0.0
