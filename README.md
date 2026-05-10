# KSP Trading App — מערכת קניות אוטומטית

מערכת Web Automation שמבצעת סריקה של מוצרים מאתר KSP, בוחרת את המוצר הזול ביותר, מוסיפה אותו לעגלת הקניות, ומצלמת מסך של דף הרכישה כהוכחת ביצוע.

---

## ארכיטקטורה (Layered Architecture)

```
frontend/          ← UI (HTML/CSS/JS) — 4 מסכים: חיפוש, סטטוס, תוצאות, קופה
api/               ← FastAPI — endpoint: POST /api/trade
services/          ← לוגיקה עסקית — תזמור השלבים + Observability logs
domain/            ← Pydantic models: Product, Cart, Order
automation/        ← Playwright — scraping + checkout + screenshot
tests/             ← pytest — unit tests + E2E tests
```

**עיקרון מרכזי:** כל הנתונים מגיעים מ-Scraping בלבד — ללא APIs חיצוניים.

---

## זרימת האוטומציה

```
1. פתיחת דפדפן (headless) ← PLAYWRIGHT_HEADLESS=true
2. ניווט לדף הבית של KSP
3. חיפוש לפי שאילתת המשתמש (הדמיית הקלדה אנושית)
4. איסוף תוצאות מה-DOM: id, title, price, currency, url, source, image_url, specs
5. בחירת המוצר הזול ביותר (get_cheapest_product)
6. הוספה לעגלת הקניות
7. מעבר לעמוד התשלום
8. מילוי פרטי משלוח
9. צילום מסך → proof_screenshot.png
```

---

## התקנה והרצה

### דרישות מקדימות
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### הרצת הבאקנד (FastAPI)
```bash
uvicorn api.main:app --reload
# זמין בכתובת: http://localhost:8000
```

### הרצת הפרונטאנד (Vanilla JS)
```bash
cd frontend
python3 -m http.server 8080
# פתח http://localhost:8080
```

---

## משתני סביבה

| משתנה | ברירת מחדל | תיאור |
|-------|-----------|-------|
| `PLAYWRIGHT_HEADLESS` | `true` | הרץ `false` לראות את הדפדפן בפעולה |

---

## הרצת הבדיקות

```bash
# כל הבדיקות (unit + E2E):
PLAYWRIGHT_HEADLESS=true pytest -v

# בדיקות יחידה בלבד:
pytest tests/test_domain_and_services.py -v

# E2E:
pytest tests/test_e2e_flow.py -v

# סוויטת 50 קטגוריות (ייקח ~10 דקות):
PLAYWRIGHT_HEADLESS=true pytest tests/test_50_categories.py -v
```

---

## פלט הבדיקות (Test Output)

```
8 passed in 0.09s
- test_product_model_validation         PASSED
- test_product_with_image_and_specs     PASSED
- test_product_currency_normalization   PASSED
- test_get_cheapest_product             PASSED
- test_get_cheapest_product_empty_list  PASSED
- test_cart_total_price                 PASSED
- test_cart_empty                       PASSED
- test_full_automation_flow             PASSED (כולל proof_screenshot.png)
```

ראה גם: `50_products_test_report.md` — 50/50 קטגוריות עברו בהצלחה.

---

## אבטחה (Security)

- `.gitignore` חוסם: `venv/`, `.env`, `__pycache__/`, `proof_screenshot.png`
- אין API keys בקוד
- כל הנתונים מ-Scraping בלבד
