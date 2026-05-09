"""
50-Category Product Search Test Suite.
Tests 50 different product queries against the KSP scraper.
Generates a detailed Markdown report: 50_products_test_report.md
Includes rate-limiting delays (3-7s) between queries to prevent IP bans.
"""
import os
import time
import random
import pytest
import asyncio
from datetime import datetime
from automation.ksp_scraper import search_products

# 50 diverse product queries covering many KSP categories
QUERIES = [
    "אייפון 15", "סמסונג גלקסי", "אוזניות בלוטוס", "מקלדת מכנית", "עכבר גיימינג",
    "מסך מחשב 27", "מחשב נייד", "טאבלט", "כבל USB-C", "מטען אלחוטי",
    "דיסק קשיח חיצוני", "כרטיס זיכרון", "רמקול בלוטוס", "מצלמת רשת", "ראוטר WiFi",
    "מדפסת", "סוללת גיבוי", "אוזניות חוטיות", "מיקרופון", "כיסוי לאייפון",
    "שעון חכם", "מסך גיימינג", "כונן SSD", "זיכרון RAM", "כרטיס מסך",
    "מעבד אינטל", "לוח אם", "ספק כוח", "מאוורר למחשב", "מארז מחשב",
    "מקרן", "טלוויזיה 55", "שואב אבק רובוט", "מכונת קפה", "מיקסר",
    "בלנדר", "טוסטר אובן", "מייבש שיער", "מגהץ", "מאוורר עמוד",
    "מזגן נייד", "תאורת LED", "מנורת שולחן", "סוללות AA", "כבל HDMI",
    "מתאם רשת", "רכזת USB", "עט סטיילוס", "משטח עכבר", "מצלמת אבטחה",
]


# Shared results list for the report
test_results = []


@pytest.fixture(scope="module")
def report_path():
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "50_products_test_report.md")


@pytest.fixture(autouse=True, scope="function")
def rate_limit_delay():
    """Add a random delay between 3-7 seconds before each test to prevent IP banning."""
    delay = random.uniform(3, 7)
    time.sleep(delay)


@pytest.mark.asyncio
@pytest.mark.parametrize("query", QUERIES, ids=[f"q{i+1}_{q[:15]}" for i, q in enumerate(QUERIES)])
async def test_search_query(query):
    """Test a single product search query."""
    os.environ["PLAYWRIGHT_HEADLESS"] = "true"
    start = time.time()
    error_msg = None
    found = 0

    try:
        products = await search_products(query, max_results=5)
        found = len(products)

        # Basic assertions
        for p in products:
            assert p.title, f"Product title should not be empty for query '{query}'"
            assert p.price > 0, f"Price should be > 0 for query '{query}'"
            assert p.product_url, f"Product URL should exist for query '{query}'"
            assert p.currency == "ILS"

    except Exception as e:
        error_msg = str(e)

    elapsed = round(time.time() - start, 2)
    status = "✅" if found > 0 else ("❌ שגיאה" if error_msg else "⚠️ 0 תוצאות")

    test_results.append({
        "query": query,
        "status": status,
        "found": found,
        "time": elapsed,
        "error": error_msg,
    })


@pytest.fixture(scope="module", autouse=True)
def generate_report(report_path):
    """Generate the Markdown report after all tests complete."""
    yield  # run all tests first

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total = len(test_results)
    success = sum(1 for r in test_results if r["found"] > 0)
    failed = total - success
    avg_time = round(sum(r["time"] for r in test_results) / max(total, 1), 2)

    lines = [
        f"# דוח בדיקת 50 קטגוריות מוצרים",
        f"",
        f"**תאריך**: {now}",
        f"",
        f"## סיכום",
        f"| מדד | ערך |",
        f"|------|------|",
        f"| סה\"כ שאילתות | {total} |",
        f"| הצלחות | {success} |",
        f"| כשלונות | {failed} |",
        f"| זמן ממוצע | {avg_time} שניות |",
        f"",
        f"## תוצאות מפורטות",
        f"",
        f"| # | שאילתה | סטטוס | מוצרים | זמן (שניות) | שגיאה |",
        f"|---|--------|--------|--------|-------------|-------|",
    ]

    for i, r in enumerate(test_results, 1):
        err = r["error"][:60] + "..." if r["error"] and len(r["error"]) > 60 else (r["error"] or "-")
        lines.append(f"| {i} | {r['query']} | {r['status']} | {r['found']} | {r['time']} | {err} |")

    lines.append("")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
