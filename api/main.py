import uuid
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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
    query: str

@app.post("/api/trade")
async def trade_endpoint(request: TradeRequest):
    """
    Receives a trade request from the UI, triggers the trading flow orchestration,
    and returns the result. Includes top-level error handling.
    """
    # Generate unique ID immediately
    request_id = str(uuid.uuid4())
    
    try:
        # Pass the execution down to the Services layer
        result = await run_trading_flow(query=request.query, request_id=request_id)
        
        return {
            "status": "success",
            "requestId": request_id,
            "data": result
        }
    except Exception as e:
        # If the automation or service layers fail, catch it here and return a friendly 500 error
        raise HTTPException(
            status_code=500, 
            detail=f"Trading automation flow failed: {str(e)}. Check backend observability logs using Request ID: {request_id}"
        )
