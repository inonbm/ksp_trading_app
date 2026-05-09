document.addEventListener('DOMContentLoaded', () => {
    const tradeForm = document.getElementById('tradeForm');
    const startBtn = document.getElementById('startBtn');

    // UI Sections
    const statusSection = document.getElementById('statusSection');
    const resultsSection = document.getElementById('resultsSection');

    // Status elements
    const loadingIndicator = document.getElementById('loadingIndicator');
    const traceList = document.getElementById('traceList');

    // Result elements
    const successMessage = document.getElementById('successMessage');
    const productDetails = document.getElementById('productDetails');
    const productTitle = document.getElementById('productTitle');
    const productPrice = document.getElementById('productPrice');
    const productUrl = document.getElementById('productUrl');

    tradeForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const query = document.getElementById('query').value.trim();
        const maxPrice = parseFloat(document.getElementById('maxPrice').value);

        if (!query) {
            alert('נא להזין שם מוצר.');
            return;
        }
        if (isNaN(maxPrice) || maxPrice <= 0) {
            alert('נא להזין מחיר מקסימלי תקין.');
            return;
        }

        setLoadingState(true);

        try {
            const response = await fetch('http://localhost:8000/api/trade', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    query: query,
                    max_price: maxPrice
                })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `שגיאת שרת: ${response.status}`);
            }

            const data = await response.json();
            renderSuccess(data);

        } catch (error) {
            renderError(error.message);
        } finally {
            setLoadingState(false, true);
        }
    });

    function setLoadingState(isLoading, requestFinished = false) {
        if (isLoading) {
            startBtn.disabled = true;
            startBtn.innerHTML = '<span>מעבד נתונים...</span>';

            statusSection.classList.remove('hidden');
            resultsSection.classList.add('hidden');
            loadingIndicator.classList.remove('hidden');
            traceList.innerHTML = '';
            productDetails.classList.remove('hidden');

            successMessage.className = '';
            successMessage.textContent = '';
        } else {
            startBtn.disabled = false;
            startBtn.innerHTML = '<span>התחל אוטומציה</span>';
            if (requestFinished) {
                loadingIndicator.classList.add('hidden');
            }
        }
    }

    function renderSuccess(data) {
        statusSection.classList.remove('hidden');
        resultsSection.classList.remove('hidden');

        // Render trace logs — backend returns flat 'trace' array
        if (data.trace && data.trace.length > 0) {
            traceList.innerHTML = data.trace.map(item => `
                <li class="trace-item">
                    <span class="trace-step">${item.step_name}</span>
                    <span class="trace-time">${item.execution_time ? item.execution_time.toFixed(2) + 's' : '-'}</span>
                </li>
            `).join('');
        } else {
            traceList.innerHTML = '<li class="trace-item"><span class="trace-step">אין נתוני מעקב</span></li>';
        }

        successMessage.className = 'success-message';
        successMessage.textContent = 'האוטומציה הושלמה בהצלחה!';

        // Product data is now at top level of response
        if (data.product) {
            productTitle.textContent = data.product.title || 'מוצר לא ידוע';
            productPrice.textContent = data.product.price || '0';

            if (data.product.product_url) {
                productUrl.href = data.product.product_url;
                productUrl.style.display = 'inline-block';
            } else {
                productUrl.style.display = 'none';
            }
        } else {
            productTitle.textContent = 'לא נמצא מוצר העונה לדרישות';
            productPrice.textContent = '0';
            productUrl.style.display = 'none';
        }
    }

    function renderError(errorMessage) {
        statusSection.classList.remove('hidden');
        resultsSection.classList.remove('hidden');

        productDetails.classList.add('hidden');

        successMessage.className = 'error-message';
        successMessage.textContent = `שגיאה בביצוע התהליך: ${errorMessage}`;

        traceList.innerHTML = `
            <li class="trace-item" style="color: var(--error-color)">
                <span class="trace-step">התהליך נכשל</span>
            </li>
        `;
    }
});
