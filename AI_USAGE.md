# AI Usage Documentation

## Tools Used
- **Code Agent / Coding Assistant**: Used for rapid scaffolding, writing boilerplates, and executing file modifications directly in the IDE.
- **Google Gemini**: Used for architectural mentoring, ensuring adherence to the strictly layered design, and troubleshooting Playwright scraping issues.

## Example Prompts
1. *"Context: We are now building the frontend layer for the KSP Trading App using strictly Vanilla HTML/JS/CSS. The backend (FastAPI) exposes a POST /api/trade endpoint... Create a clean layout with a Search section and a Status/Trace section."*
2. *"Implement the test suite using pytest. Update Environment by adding pytest and pytest-asyncio. Create tests to verify the Product Pydantic model correctly normalizes data..."*
3. *"Fix the Playwright automation logic and overhaul the UI. Convert the app to Hebrew and translate all text. Fix the 404 bug by navigating to the KSP homepage instead of a direct internal search URL."*

## AI Bugs/Mistakes and Fixes
**Major Mistake (404 Routing Error):** 
During the initial automation implementation, the AI attempted to navigate directly to KSP's internal search endpoint via the URL: `https://ksp.co.il/web/search?q={query}`. Modern web applications built on React/NextJS often use dynamic client-side routing, and directly hitting such deep links via a headless browser resulted in a `404 Not Found` page or triggered an anti-bot block.

**The Fix:**
We resolved this by instructing the AI to emulate human behavior. Instead of hitting the internal API directly, the Playwright script was refactored to:
1. Navigate to the root homepage (`https://ksp.co.il/`).
2. Robustly locate the search bar dynamically using generic selectors.
3. Simulate typing the query and pressing the `Enter` key.
This successfully bypassed the 404 error and allowed KSP's native JavaScript frontend routing to handle the search normally.

## Secret Leak Prevention
From the very beginning of the project, we enforced strict repository hygiene. Before committing any code, a comprehensive `.gitignore` file was created by the AI. This explicitly ignored `.env` files, `__pycache__`, the `venv/` directory, and local testing outputs like the Playwright screenshots (`proof_screenshot.png`). This preemptive approach guaranteed that no API keys, credentials, or local environment paths were ever pushed to the public GitHub repository.
