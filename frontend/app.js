document.addEventListener('DOMContentLoaded', () => {
    const tradeForm = document.getElementById('tradeForm');
    const startBtn = document.getElementById('startBtn');
    const statusSection = document.getElementById('statusSection');
    const loadingIndicator = document.getElementById('loadingIndicator');
    const traceContainer = document.getElementById('traceContainer');
    const traceList = document.getElementById('traceList');
    const catalogSection = document.getElementById('catalogSection');
    const catalogTitle = document.getElementById('catalogTitle');
    const productCount = document.getElementById('productCount');
    const productGrid = document.getElementById('productGrid');
    const errorSection = document.getElementById('errorSection');
    const errorMessage = document.getElementById('errorMessage');

    const stepNameMap = {
        'search_products': 'חיפוש מוצרים',
        'get_cheapest_product': 'בחירת המוצר הזול ביותר',
        'add_to_cart_and_checkout': 'הוספה לעגלה ומעבר לקופה'
    };

    function translateStep(name) { return stepNameMap[name] || name; }

    tradeForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const query = document.getElementById('query').value.trim();
        const maxPrice = parseFloat(document.getElementById('maxPrice').value);

        if (!query) { alert('נא להזין שם מוצר.'); return; }
        if (isNaN(maxPrice) || maxPrice <= 0) { alert('נא להזין מחיר מקסימלי תקין.'); return; }

        // Reset UI
        startBtn.disabled = true;
        startBtn.innerHTML = '<span>⏳ סורק...</span>';
        statusSection.classList.remove('hidden');
        loadingIndicator.classList.remove('hidden');
        traceContainer.classList.add('hidden');
        catalogSection.classList.add('hidden');
        errorSection.classList.add('hidden');
        traceList.innerHTML = '';
        productGrid.innerHTML = '';

        try {
            const response = await fetch('http://localhost:8000/api/trade', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query, max_price: maxPrice })
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.detail || `שגיאת שרת: ${response.status}`);
            }

            const data = await response.json();
            renderResults(data, query);

        } catch (error) {
            renderError(error.message);
        } finally {
            startBtn.disabled = false;
            startBtn.innerHTML = '<span>🔍 חפש מוצרים</span>';
            loadingIndicator.classList.add('hidden');
        }
    });

    function renderResults(data, query) {
        // Show trace
        if (data.trace && data.trace.length > 0) {
            traceContainer.classList.remove('hidden');
            traceList.innerHTML = data.trace.map(item => `
                <li class="trace-item">
                    <span class="trace-step">${translateStep(item.step_name)}</span>
                    <span class="trace-time">${item.execution_time ? item.execution_time.toFixed(2) + ' שניות' : '-'}</span>
                </li>
            `).join('');
        }

        // Show catalog
        const products = data.products || [];
        if (products.length === 0) {
            renderError('לא נמצאו מוצרים התואמים לחיפוש.');
            return;
        }

        catalogSection.classList.remove('hidden');
        catalogTitle.textContent = `תוצאות עבור "${query}"`;
        productCount.textContent = `${products.length} מוצרים`;

        productGrid.innerHTML = products.map(product => `
            <div class="product-card">
                ${product.image_url
                    ? `<img class="product-card-image" src="${product.image_url}" alt="${product.title}" loading="lazy">`
                    : `<div class="product-card-image-placeholder">📦</div>`
                }
                <div class="product-card-body">
                    <div class="product-card-title">${product.title}</div>
                    ${product.specs ? `<div class="product-card-specs">${product.specs}</div>` : ''}
                    <div class="product-card-price">${product.price.toLocaleString()} ₪</div>
                    <a href="${product.product_url}" target="_blank" class="product-card-link">צפה ב-KSP</a>
                </div>
            </div>
        `).join('');
    }

    function renderError(msg) {
        errorSection.classList.remove('hidden');
        errorMessage.textContent = `שגיאה: ${msg}`;
    }
});
