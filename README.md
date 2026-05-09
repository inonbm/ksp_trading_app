# KSP Trading App

A fully automated web trading application that scrapes product data from KSP, selects the cheapest matching product, and automates the checkout process using Playwright.

## Architecture Overview
The application strictly follows a layered architecture to ensure separation of concerns:
- **`frontend`**: A Vanilla HTML/JS/CSS client offering a modern RTL Hebrew interface for interacting with the backend.
- **`api`**: A FastAPI layer exposing the REST endpoints (e.g., `POST /api/trade`).
- **`services`**: The core business logic orchestrating the steps (`run_trading_flow`).
- **`domain`**: Pydantic models (`Product`, `Cart`, `Order`) strictly enforcing data normalization and validation.
- **`automation`**: Playwright scripts responsible for interacting with the external KSP website (scraping and checkout).

## Setup and Run Instructions

### 1. Backend Setup
Activate your Python virtual environment (if using one) and install dependencies:
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

Run the FastAPI backend server:
```bash
uvicorn api.main:app --reload
```
*(The backend will be available at `http://localhost:8000`)*

### 2. Frontend Setup
In a new terminal window, serve the static frontend files:
```bash
cd frontend
python3 -m http.server 8080
```
*(Access the web app at `http://localhost:8080`)*

## Testing
The project includes a comprehensive `pytest` suite covering unit and end-to-end flows.
To run the tests, execute:
```bash
pytest -v
```

## Automation Flow
1. **Navigate & Search**: Playwright navigates to KSP's homepage and emulates human typing to submit the query.
2. **Select Cheapest**: The system extracts all search results, normalizes them via Pydantic, and identifies the cheapest item within the max price constraint.
3. **Add to Cart**: Automates clicking the "Add to Cart" and "Proceed to Checkout" buttons.
4. **Capture Proof**: Generates a `proof_screenshot.png` of the cart to verify successful execution.
