# AI Bugs and Mistakes Documentation

This document records AI-generated bugs encountered during development and how they were fixed.

## Bug 1: 404 Error – Direct URL Navigation
**What happened:** The AI initially navigated directly to `https://ksp.co.il/web/search?q={query}`. KSP's React-based frontend uses client-side routing, so this deep link returned a 404 error page in the headless browser.

**Fix:** Refactored the automation to navigate to the KSP homepage (`https://ksp.co.il/`), dynamically locate the search bar using `get_by_placeholder` with a Hebrew regex, and simulate human typing with `page.keyboard.type()` followed by pressing Enter.

## Bug 2: Stale Locator After Auto-Suggest
**What happened:** After typing into the KSP search bar, the AI used `search_input.press('Enter')` on the original locator. KSP's auto-suggest dropdown caused a React re-render that detached the original `<input>` element from the DOM. The `.press()` call hung indefinitely (30s timeout).

**Fix:** Switched from `search_input.fill()` + `search_input.press('Enter')` to `search_input.click()` + `page.keyboard.type()` + `page.keyboard.press('Enter')`. The `page.keyboard` API sends keystrokes to whatever element currently has focus, completely bypassing the stale DOM reference issue.

## Bug 3: Unstable CSS Selectors
**What happened:** The AI initially used `input[type="search"]` and `input[placeholder*="חיפוש"]` as CSS selectors. These were too specific and broke when KSP's frontend updated the placeholder text or input type.

**Fix:** Implemented a multi-tier fallback strategy:
1. Primary: `page.get_by_placeholder(re.compile(r"חפש|חיפוש|search", re.IGNORECASE))`
2. Fallback: `page.locator('input[type="search"], input[type="text"]').first`
3. Added `page.keyboard.press("Escape")` before search to dismiss any blocking popups/modals.

## Bug 4: Missing Retry Mechanism
**What happened:** The AI did not implement any retry logic for flaky Playwright operations. A single network hiccup or slow page load would crash the entire flow.

**Fix:** Wrapped both `search_products` and `add_to_cart_and_checkout` in retry loops (`MAX_RETRIES = 2`), logging each failed attempt before retrying.
