import uuid
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
from services.trading_service import run_trading_flow
from services.checkout_service import run_checkout_flow

logging.basicConfig(level=logging.INFO, format="%(message)s")

app = FastAPI(title="KSP Automation Trading API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TradeRequest(BaseModel):
    """Search request from UI — triggers scraping."""
    query: str = Field(..., min_length=1, description="Product search query")
    max_price: float = Field(default=None, ge=0, description="Optional max price filter in ILS")


class CartProduct(BaseModel):
    """A product the user selected from the UI catalog."""
    id: str
    title: str
    price: float
    product_url: str
    currency: str = "ILS"
    source: str = "KSP"
    image_url: Optional[str] = None
    specs: Optional[str] = None


class UserDetails(BaseModel):
    """Shipping / personal details for auto-fill at checkout."""
    full_name: str = "ישראל ישראלי"
    phone: str = "0501234567"
    email: str = "test@example.com"
    city: str = "תל אביב"
    street: str = "הרצל 1"


class CheckoutRequest(BaseModel):
    """Cart checkout request — user-chosen products + their details."""
    products: List[CartProduct]
    user_details: UserDetails = Field(default_factory=UserDetails)


@app.post("/api/trade")
async def trade_endpoint(request: TradeRequest):
    """
    Scrape KSP for products matching the query.
    Returns full sorted catalog for the storefront UI.
    """
    request_id = str(uuid.uuid4())
    try:
        result = await run_trading_flow(query=request.query, request_id=request_id)

        products = result.get("products", [])
        if request.max_price is not None:
            products = [p for p in products if p["price"] <= request.max_price]

        return {
            "status": "success",
            "requestId": request_id,
            "products": products,
            "total_found": len(products),
            "trace": [
                {
                    "step_name": step["step"],
                    "execution_time": step["execution_time"],
                    "status": step["status"]
                }
                for step in result.get("trace_details", [])
            ]
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"שגיאה בתהליך החיפוש: {str(e)}. מזהה בקשה: {request_id}"
        )


@app.post("/api/checkout")
async def checkout_endpoint(request: CheckoutRequest):
    """
    Takes the user's cart and personal details.
    Launches Playwright to add each product to KSP cart, navigate to checkout,
    fill shipping details, and capture a proof screenshot.
    """
    request_id = str(uuid.uuid4())
    try:
        result = await run_checkout_flow(
            products=[p.model_dump() for p in request.products],
            user_details=request.user_details.model_dump(),
            request_id=request_id
        )
        return {
            "status": "success",
            "requestId": request_id,
            "message": f"הרכישה הושלמה עבור {len(request.products)} מוצרים",
            "screenshot": result.get("screenshot_path"),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"שגיאה בתהליך הרכישה: {str(e)}. מזהה בקשה: {request_id}"
        )
