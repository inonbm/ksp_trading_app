from typing import List
from pydantic import BaseModel, Field

class Product(BaseModel):
    """
    Represents a normalized product scraped from a target website (e.g., KSP).
    """
    id: str = Field(..., description="Unique identifier for the product")
    title: str = Field(..., description="The name or title of the product")
    price: float = Field(..., ge=0, description="The price of the product. Must be non-negative.")
    currency: str = Field(..., description="The currency of the price (e.g., ILS, USD)")
    product_url: str = Field(..., description="The direct URL to the product page")
    source: str = Field(..., description="The source website where the product was scraped from, e.g., 'KSP'")

class Cart(BaseModel):
    """
    Represents a shopping cart containing multiple products.
    """
    items: List[Product] = Field(default_factory=list, description="List of products in the cart")

    @property
    def total_price(self) -> float:
        """
        Computed property to calculate the total price of all items in the cart.
        """
        return sum(item.price for item in self.items)

class Order(BaseModel):
    """
    Represents a final order, containing the cart details, shipping, and status.
    """
    cart: Cart = Field(..., description="The cart containing the items ordered")
    shipping_details: str = Field(..., description="Address or details for shipping")
    order_status: str = Field(default="PENDING", description="The current status of the order (e.g., PENDING, COMPLETED, FAILED)")
