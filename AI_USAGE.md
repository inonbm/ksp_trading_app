# שקיפות שימוש בבינה מלאכותית (AI Usage)

## כלים בהם השתמשנו
- **Google Gemini (Antigravity Agent)**: לכתיבת קוד, ניפוי באגים, עיצוב ארכיטקטורה, ובניית בדיקות.
- **Playwright Inspector**: לבדיקת ה-DOM של KSP בזמן אמת.

---

## 3–5 בקשות (Prompts) אמיתיות שכתבנו ל-AI

**Prompt 1 – בניית הארכיטקטורה:**
> "Context: We are now building the frontend layer for the KSP Trading App using strictly Vanilla HTML/JS/CSS. The backend (FastAPI) exposes a POST /api/trade endpoint. Create a clean layout with a Search section, a Status/Trace section, and a Results/Checkout section. All text must be in Hebrew."

**Prompt 2 – תיקון אוטומציית Playwright:**
> "Fix the Playwright automation logic. BUG: Navigating directly to ksp.co.il/web/search?q={query} results in a 404. FIX: Emulate real human behavior. Navigate to the KSP homepage, press Escape to dismiss popups, locate the search bar using Hebrew placeholder regex, type the query and press Enter."

**Prompt 3 – תיקון בחירת תמונה:**
> "The scraper returns the KSP logo instead of product images. Investigate: KSP uses CSS-module class imageWrapperLink-* for product image containers. Fix the extraction to target that specific element instead of any ancestor img."

**Prompt 4 – אופטימיזציית ביצועים:**
> "The scraper takes 5-7 minutes per search. Optimize: set headless=True by default, add --disable-images browser flag, reduce typing delay from 50ms to 20ms, replace 4 scroll steps + networkidle wait with a single 1500px scroll, cut timeouts to 10s global."

**Prompt 5 – ישור קו מול דרישות המטלה:**
> "Audit the entire project against the assignment spec: Section 4 requires the full flow Search→Select Cheapest→Add to Cart→Screenshot. Section 3 requires 4 UI screens. Section 7 requires E2E test validating proof_screenshot.png. Restore and fix all missing pieces."

---

## שגיאות ה-AI ואיך תיקנו אותן

### שגיאה 1: ניווט ישיר ל-URL פנימי (404)
**מה ה-AI עשה:** ניסה לנווט ישירות ל-`https://ksp.co.il/web/search?q=query`. KSP בנויה על React עם Client-Side Routing, ולכן הדפדפן קיבל דף 404.

**התיקון:** שינינו לניווט לדף הבית של KSP, זיהוי שורת החיפוש לפי placeholder בעברית, והדמיית הקלדה אנושית עם `page.keyboard`.

### שגיאה 2: Stale Locator לאחר Auto-Suggest
**מה ה-AI עשה:** השתמש ב-`search_input.press('Enter')` על ה-locator המקורי. KSP מבצעת re-render של ה-input כאשר מוצג חלון Auto-Suggest, מה שגרם ל-locator להפוך ל"מת" (detached).

**התיקון:** מעבר ל-`search_input.click()` + `page.keyboard.type()` + `page.keyboard.press('Enter')`. ה-API של `page.keyboard` שולח מקשים לאלמנט שבפוקוס, ללא תלות ב-DOM reference.

### שגיאה 3: חילוץ תמונת הלוגו במקום תמונת המוצר
**מה ה-AI עשה:** השתמש ב-`ancestor::div[.//img]` שמצא כל `<img>` בדף, כולל לוגו KSP שמופיע בכותרת.

**התיקון:** זיהינו שKSP משתמשת במחלקת CSS-Module `imageWrapperLink-*` עבור תמונות המוצר. שינינו לסלקטור `a[class*="imageWrapperLink"]` שמדויק לחלוטין.

### שגיאה 4: זמן ביצוע של 5–7 דקות
**מה ה-AI עשה:** השתמש ב-`headless=False` כברירת מחדל, 4 גלילות + המתנה ל-networkidle, ו-50ms delay לכל הקשה.

**התיקון:** הגדרנו `headless=True` כברירת מחדל, הוספנו `--disable-images` כ-browser flag, קיצרנו ל-גלילה אחת של 1500px, והורדנו delay ל-20ms. הביצוע ירד מ-7 דקות ל-**~4 שניות**.

---

## שמירת סודות (Secret Prevention)
- **`.gitignore`** מוגדר מראש עם חסימה מלאה של: `.env`, `venv/`, `__pycache__/`, `proof_screenshot.png`, קבצי מפתח, ועוד.
- **אין API keys** בקוד — כל הנתונים מגיעים מ-Scraping בלבד (ללא שירותים חיצוניים).
- **לא הועברו לAI** פרטי גישה, סיסמאות, או מידע רגיש. כל שאלות ה-AI היו על קוד טכני בלבד.
