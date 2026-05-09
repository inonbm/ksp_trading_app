import uuid
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from services.trading_service import run_trading_flow

# Initialize basic configuration for JSON logs to print cleanly to the console
logging.basicConfig(level=logging.INFO, format="%(message)s")

app = FastAPI(title="KSP Automation Trading API")

# Setup CORS to allow the Vanilla JS frontend to communicate with this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TradeRequest(BaseModel):
    """Input validation for the trade request from the UI (Section 4.2)."""
    query: str = Field(..., min_length=1, description="Product search query")
    max_price: float = Field(default=None, ge=0, description="Optional maximum price filter in ILS")

@app.post("/api/trade")
async def trade_endpoint(request: TradeRequest):
    """
    Receives a trade request from the UI, triggers the trading flow orchestration,
    and returns the result including trace details for the frontend to display.
    """
    request_id = str(uuid.uuid4())

    try:
        result = await run_trading_flow(query=request.query, request_id=request_id)

        return {
            "status": "success",
            "requestId": request_id,
            "product": result.get("product"),
            "order_status": result.get("order_status"),
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
            detail=f"שגיאה בתהליך האוטומציה: {str(e)}. מזהה בקשה: {request_id}"
        )
