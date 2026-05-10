document.addEventListener('DOMContentLoaded', () => {
    const tradeForm        = document.getElementById('tradeForm');
    const startBtn         = document.getElementById('startBtn');
    const statusSection    = document.getElementById('statusSection');
    const loadingIndicator = document.getElementById('loadingIndicator');
    const traceContainer   = document.getElementById('traceContainer');
    const traceList        = document.getElementById('traceList');
    const catalogSection   = document.getElementById('catalogSection');
    const productCount     = document.getElementById('productCount');
    const productGrid      = document.getElementById('productGrid');
    const checkoutSection  = document.getElementById('checkoutSection');
    const selectedProductCard = document.getElementById('selectedProductCard');
    const checkoutStatus   = document.getElementById('checkoutStatus');
    const screenshotContainer = document.getElementById('screenshotContainer');
    const errorSection     = document.getElementById('errorSection');
    const errorMessage     = document.getElementById('errorMessage');

    // Hebrew translation for trace step names
    const stepNameMap = {
        'search_products':         'חיפוש מוצרים',
        'get_cheapest_product':    'בחירת המוצר הזול ביותר',
        'add_to_cart_and_checkout':'הוספה לעגלה ומעבר לקופה'
    };
    const translateStep = name => stepNameMap[name] || name;
    const stepIcon = status => status === 'success' ? '✅' : '❌';

    // ── Form submit ──────────────────────────────────────────────────────────
    tradeForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const query    = document.getElementById('query').value.trim();
        const maxPrice = parseFloat(document.getElementById('maxPrice').value);

        if (!query)                          { alert('נא להזין שם מוצר.');              return; }
        if (isNaN(maxPrice) || maxPrice <= 0){ alert('נא להזין מחיר מקסימלי תקין.');   return; }

        resetUI();
        setLoading(true);

        try {
            const response = await fetch('http://localhost:8000/api/trade', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query, max_price: maxPrice })
            });

            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.detail || `שגיאת שרת: ${response.status}`);
            }

            const data = await response.json();
            renderTrace(data.trace || []);
            renderCatalog(data.products || [], query);
            renderCheckout(data.selected_product, data.order_status, data.trace || []);

        } catch (error) {
            renderError(error.message);
        } finally {
            setLoading(false);
        }
    });

    // ── UI helpers ───────────────────────────────────────────────────────────
    function resetUI() {
        [statusSection, catalogSection, checkoutSection, errorSection].forEach(s =>
            s.classList.add('hidden'));
        traceContainer.classList.add('hidden');
        traceList.innerHTML   = '';
        productGrid.innerHTML = '';
        selectedProductCard.innerHTML = '';
        checkoutStatus.innerHTML = '';
        screenshotContainer.classList.add('hidden');
        errorSection.classList.add('hidden');
    }

    function setLoading(on) {
        startBtn.disabled = on;
        startBtn.innerHTML = on
            ? '<span>⏳ האוטומציה רצה...</span>'
            : '<span>🚀 התחל אוטומציה</span>';
        statusSection.classList.remove('hidden');
        loadingIndicator.classList.toggle('hidden', !on);
    }

    // ── Screen ②: Trace ──────────────────────────────────────────────────────
    function renderTrace(trace) {
        if (!trace.length) return;
        traceContainer.classList.remove('hidden');
        traceList.innerHTML = trace.map(item => `
            <li class="trace-item ${item.status}">
                <span class="trace-icon">${stepIcon(item.status)}</span>
                <span class="trace-step">${translateStep(item.step_name)}</span>
                <span class="trace-time">${item.execution_time
                    ? item.execution_time.toFixed(2) + ' שניות' : '-'}</span>
            </li>
        `).join('');
    }

    // ── Screen ③: Catalog ────────────────────────────────────────────────────
    function renderCatalog(products, query) {
        if (!products.length) {
            renderError('לא נמצאו מוצרים התואמים לחיפוש ולמחיר המקסימלי שהוגדר.');
            return;
        }
        catalogSection.classList.remove('hidden');
        productCount.textContent = `${products.length} מוצרים`;

        productGrid.innerHTML = products.map(p => `
            <div class="product-card">
                ${p.image_url
                    ? `<img class="product-card-image" src="${p.image_url}" alt="${p.title}" loading="lazy">`
                    : `<div class="product-card-image-placeholder">📦</div>`}
                <div class="product-card-body">
                    <div class="product-card-title">${p.title}</div>
                    ${p.specs ? `<div class="product-card-specs">${p.specs}</div>` : ''}
                    <div class="product-card-price">${p.price.toLocaleString()} ₪</div>
                    <a href="${p.product_url}" target="_blank" class="product-card-link">
                        צפה ב-KSP ↗
                    </a>
                </div>
            </div>
        `).join('');
    }

    // ── Screen ④: Checkout ───────────────────────────────────────────────────
    function renderCheckout(selectedProduct, orderStatus, trace) {
        checkoutSection.classList.remove('hidden');

        const checkoutStep = trace.find(t => t.step_name === 'add_to_cart_and_checkout');
        const checkoutOk   = checkoutStep?.status === 'success';

        // Selected product card
        if (selectedProduct) {
            selectedProductCard.innerHTML = `
                <div class="selected-label">🏆 המוצר שנבחר אוטומטית (הזול ביותר)</div>
                ${selectedProduct.image_url
                    ? `<img class="selected-img" src="${selectedProduct.image_url}" alt="${selectedProduct.title}">`
                    : ''}
                <div class="selected-title">${selectedProduct.title}</div>
                <div class="selected-price">${selectedProduct.price?.toLocaleString()} ₪</div>
                <a href="${selectedProduct.product_url}" target="_blank" class="product-card-link">
                    צפה ב-KSP ↗
                </a>
            `;
        }

        // Order status badge
        if (checkoutOk) {
            checkoutStatus.innerHTML = `
                <div class="status-badge success">
                    ✅ הוספה לעגלה הושלמה — ${orderStatus || 'ממתין לאישור'}
                </div>`;
            screenshotContainer.classList.remove('hidden');
        } else {
            checkoutStatus.innerHTML = `
                <div class="status-badge warning">
                    ⚠️ שלב הקופה לא הושלם — ייתכן שנדרשת כניסה לחשבון ב-KSP.
                    צילום המסך נשמר בשרת אם הדפדפן הגיע לעמוד הרכישה.
                </div>`;
            screenshotContainer.classList.remove('hidden');
        }
    }

    // ── Error ────────────────────────────────────────────────────────────────
    function renderError(msg) {
        errorSection.classList.remove('hidden');
        errorMessage.textContent = `שגיאה: ${msg}`;
    }
});
