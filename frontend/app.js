document.addEventListener('DOMContentLoaded', () => {

    /* ══════════════════════════════════════════════
       DOM refs
    ══════════════════════════════════════════════ */
    // Search
    const tradeForm        = document.getElementById('tradeForm');
    const startBtn         = document.getElementById('startBtn');
    const statusSection    = document.getElementById('statusSection');
    const loadingIndicator = document.getElementById('loadingIndicator');
    const traceContainer   = document.getElementById('traceContainer');
    const traceList        = document.getElementById('traceList');
    const catalogSection   = document.getElementById('catalogSection');
    const productCount     = document.getElementById('productCount');
    const productGrid      = document.getElementById('productGrid');
    const checkoutResultSection = document.getElementById('checkoutResultSection');
    const checkoutResultContent = document.getElementById('checkoutResultContent');
    const errorSection     = document.getElementById('errorSection');
    const errorMessage     = document.getElementById('errorMessage');

    // Cart drawer
    const cartDrawer       = document.getElementById('cartDrawer');
    const cartOverlay      = document.getElementById('cartOverlay');
    const cartFab          = document.getElementById('cartFab');
    const cartBadge        = document.getElementById('cartBadge');
    const cartCloseBtn     = document.getElementById('cartCloseBtn');
    const cartItems        = document.getElementById('cartItems');
    const cartEmpty        = document.getElementById('cartEmpty');
    const cartTotal        = document.getElementById('cartTotal');
    const cartFooter       = document.getElementById('cartFooter');
    const checkoutBtn      = document.getElementById('checkoutBtn');
    const clearCartBtn     = document.getElementById('clearCartBtn');

    // User details inputs
    const userFullName     = document.getElementById('userFullName');
    const userPhone        = document.getElementById('userPhone');
    const userEmail        = document.getElementById('userEmail');
    const userCity         = document.getElementById('userCity');
    const userStreet       = document.getElementById('userStreet');

    /* ══════════════════════════════════════════════
       Cart state  (persisted in localStorage)
    ══════════════════════════════════════════════ */
    let cart = JSON.parse(localStorage.getItem('ksp_cart') || '[]');

    function saveCart() {
        localStorage.setItem('ksp_cart', JSON.stringify(cart));
    }

    function isInCart(productUrl) {
        return cart.some(item => item.product_url === productUrl);
    }

    function addToCart(product) {
        if (isInCart(product.product_url)) return;
        cart.push(product);
        saveCart();
        renderCart();
        refreshCardStates();
    }

    function removeFromCart(productUrl) {
        cart = cart.filter(item => item.product_url !== productUrl);
        saveCart();
        renderCart();
        refreshCardStates();
    }

    function clearCart() {
        cart = [];
        saveCart();
        renderCart();
        refreshCardStates();
    }

    /* ══════════════════════════════════════════════
       Render Cart Drawer
    ══════════════════════════════════════════════ */
    function renderCart() {
        // Badge
        if (cart.length > 0) {
            cartBadge.textContent = cart.length;
            cartBadge.classList.remove('hidden');
        } else {
            cartBadge.classList.add('hidden');
        }

        // Empty state
        cartEmpty.classList.toggle('hidden', cart.length > 0);

        // Remove old item rows (keep cartEmpty)
        cartItems.querySelectorAll('.cart-item').forEach(el => el.remove());

        // Add item rows
        cart.forEach(product => {
            const row = document.createElement('div');
            row.className = 'cart-item';
            row.dataset.url = product.product_url;
            row.innerHTML = `
                ${product.image_url
                    ? `<img class="cart-item-img" src="${product.image_url}" alt="${product.title}" loading="lazy">`
                    : `<span class="cart-item-img-placeholder">📦</span>`}
                <div class="cart-item-info">
                    <div class="cart-item-title">${product.title}</div>
                    <div class="cart-item-price">${product.price.toLocaleString()} ₪</div>
                </div>
                <button class="cart-item-remove" aria-label="הסר מהעגלה">✕</button>
            `;
            row.querySelector('.cart-item-remove').addEventListener('click', () => {
                removeFromCart(product.product_url);
            });
            cartItems.appendChild(row);
        });

        // Total
        const total = cart.reduce((sum, p) => sum + p.price, 0);
        cartTotal.textContent = `${total.toLocaleString()} ₪`;

        // Checkout button
        checkoutBtn.disabled = cart.length === 0;
    }

    // Refresh "הוסף לעגלה" button state on all visible product cards
    function refreshCardStates() {
        document.querySelectorAll('.product-card').forEach(card => {
            const url = card.dataset.productUrl;
            const btn = card.querySelector('.btn-add-cart');
            if (!btn || !url) return;
            const inCart = isInCart(url);
            btn.textContent = inCart ? '✓ בעגלה' : '+ הוסף לעגלה';
            btn.classList.toggle('added', inCart);
            card.classList.toggle('in-cart', inCart);
        });
    }

    /* ══════════════════════════════════════════════
       Cart drawer open / close
    ══════════════════════════════════════════════ */
    function openCart()  {
        cartDrawer.classList.remove('hidden');
        cartOverlay.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
    }
    function closeCart() {
        cartDrawer.classList.add('hidden');
        cartOverlay.classList.add('hidden');
        document.body.style.overflow = '';
    }

    cartFab.addEventListener('click', openCart);
    cartCloseBtn.addEventListener('click', closeCart);
    cartOverlay.addEventListener('click', closeCart);
    clearCartBtn.addEventListener('click', clearCart);

    /* ══════════════════════════════════════════════
       Checkout — validate → send to backend → Playwright
    ══════════════════════════════════════════════ */
    checkoutBtn.addEventListener('click', async () => {
        if (cart.length === 0) return;

        // ── Validate required fields ────────────────────────────────────────
        const requiredFields = [
            { el: userFullName, label: 'שם מלא' },
            { el: userPhone,    label: 'טלפון' },
            { el: userEmail,    label: 'אימייל' },
            { el: userCity,     label: 'עיר' },
            { el: userStreet,   label: 'רחוב ומספר' },
        ];
        requiredFields.forEach(f => f.el.classList.remove('input-error'));
        const missing = requiredFields.filter(f => !f.el.value.trim());
        if (missing.length > 0) {
            missing.forEach(f => f.el.classList.add('input-error'));
            missing[0].el.focus();
            return;
        }

        const userDetails = {
            full_name: userFullName.value.trim(),
            phone:     userPhone.value.trim(),
            email:     userEmail.value.trim(),
            city:      userCity.value.trim(),
            street:    userStreet.value.trim(),
        };

        checkoutBtn.disabled = true;
        checkoutBtn.innerHTML = '<span>⏳ האוטומציה פועלת... אנא המתן</span>';


        try {
            const resp = await fetch('http://localhost:8000/api/checkout', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    products: cart.map(p => ({
                        id: p.id, title: p.title, price: p.price,
                        product_url: p.product_url, currency: p.currency,
                        source: p.source, image_url: p.image_url, specs: p.specs
                    })),
                    user_details: userDetails
                })
            });

            const data = await resp.json();

            checkoutResultSection.classList.remove('hidden');
            checkoutResultSection.scrollIntoView({ behavior: 'smooth' });
            closeCart();

            if (resp.ok && data.status === 'success') {
                checkoutResultContent.innerHTML = `
                    <div class="status-badge success">
                        ✅ הרכישה הושלמה! הדפדפן הגיע לעמוד הקופה ב-KSP.<br>
                        צילום מסך נשמר בשרת: <code>proof_screenshot.png</code><br>
                        <small>מוצרים שנרכשו: ${cart.map(p => p.title.split(' ').slice(0,4).join(' ')).join(' | ')}</small>
                    </div>`;
                clearCart();
            } else {
                const detail = data.detail || 'שגיאה לא ידועה';
                checkoutResultContent.innerHTML = `
                    <div class="status-badge warning">
                        ⚠️ שלב הקופה לא הושלם: ${detail}<br>
                        <small>ייתכן שנדרשת כניסה לחשבון ב-KSP. הצילום נשמר אם הדפדפן הגיע לעמוד.</small>
                    </div>`;
            }
        } catch (err) {
            checkoutResultContent.innerHTML = `
                <div class="status-badge warning">
                    ⚠️ לא ניתן לתקשר עם השרת: ${err.message}
                </div>`;
            checkoutResultSection.classList.remove('hidden');
        } finally {
            checkoutBtn.disabled = cart.length === 0;
            checkoutBtn.innerHTML = '<span>🚀 מעבר לרכישה ב-KSP</span>';
        }
    });

    /* ══════════════════════════════════════════════
       Trace step translation
    ══════════════════════════════════════════════ */
    const stepNameMap = {
        'search_products':          'חיפוש מוצרים',
        'get_cheapest_product':     'בחירת המוצר הזול ביותר',
        'add_to_cart_and_checkout': 'הוספה לעגלה ומעבר לקופה'
    };
    const translateStep = name => stepNameMap[name] || name;
    const stepIcon      = status => status === 'success' ? '✅' : '❌';

    /* ══════════════════════════════════════════════
       Search form submit
    ══════════════════════════════════════════════ */
    tradeForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const query    = document.getElementById('query').value.trim();
        const maxPrice = parseFloat(document.getElementById('maxPrice').value);

        if (!query)                           { alert('נא להזין שם מוצר.');            return; }
        if (isNaN(maxPrice) || maxPrice <= 0) { alert('נא להזין מחיר מקסימלי תקין.'); return; }

        resetSearchUI();
        setLoading(true);

        try {
            const resp = await fetch('http://localhost:8000/api/trade', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query, max_price: maxPrice })
            });

            if (!resp.ok) {
                const err = await resp.json().catch(() => ({}));
                throw new Error(err.detail || `שגיאת שרת: ${resp.status}`);
            }

            const data = await resp.json();
            renderTrace(data.trace || []);
            renderCatalog(data.products || [], query);

        } catch (err) {
            renderError(err.message);
        } finally {
            setLoading(false);
        }
    });

    /* ══════════════════════════════════════════════
       UI helpers
    ══════════════════════════════════════════════ */
    function resetSearchUI() {
        [statusSection, catalogSection, checkoutResultSection, errorSection].forEach(
            s => s.classList.add('hidden'));
        traceContainer.classList.add('hidden');
        traceList.innerHTML   = '';
        productGrid.innerHTML = '';
        checkoutResultContent.innerHTML = '';
        errorSection.classList.add('hidden');
    }

    function setLoading(on) {
        startBtn.disabled = on;
        startBtn.innerHTML = on
            ? '<span>⏳ סורק...</span>'
            : '<span>🔍 חפש מוצרים</span>';
        statusSection.classList.remove('hidden');
        loadingIndicator.classList.toggle('hidden', !on);
    }

    function renderTrace(trace) {
        if (!trace.length) return;
        traceContainer.classList.remove('hidden');
        traceList.innerHTML = trace.map(item => `
            <li class="trace-item ${item.status}">
                <span class="trace-icon">${stepIcon(item.status)}</span>
                <span class="trace-step">${translateStep(item.step_name)}</span>
                <span class="trace-time">${item.execution_time
                    ? item.execution_time.toFixed(2) + 's' : '-'}</span>
            </li>
        `).join('');
    }

    function renderCatalog(products, query) {
        if (!products.length) {
            renderError('לא נמצאו מוצרים התואמים לחיפוש.');
            return;
        }
        catalogSection.classList.remove('hidden');
        productCount.textContent = `${products.length} מוצרים`;

        productGrid.innerHTML = products.map(p => `
            <div class="product-card ${isInCart(p.product_url) ? 'in-cart' : ''}"
                 data-product-url="${p.product_url}">
                ${p.image_url
                    ? `<img class="product-card-image" src="${p.image_url}" alt="${p.title}" loading="lazy">`
                    : `<div class="product-card-image-placeholder">📦</div>`}
                <div class="product-card-body">
                    <div class="product-card-title">${p.title}</div>
                    ${p.specs ? `<div class="product-card-specs">${p.specs}</div>` : ''}
                    <div class="product-card-price">${p.price.toLocaleString()} ₪</div>
                </div>
                <div class="product-card-actions">
                    <button class="btn-add-cart ${isInCart(p.product_url) ? 'added' : ''}">
                        ${isInCart(p.product_url) ? '✓ בעגלה' : '+ הוסף לעגלה'}
                    </button>
                    <a href="${p.product_url}" target="_blank" class="btn-view-ksp" title="צפה ב-KSP">↗</a>
                </div>
            </div>
        `).join('');

        // Bind "Add to Cart" buttons
        productGrid.querySelectorAll('.product-card').forEach((card, i) => {
            const product = products[i];
            card.querySelector('.btn-add-cart').addEventListener('click', () => {
                if (isInCart(product.product_url)) return;
                addToCart(product);
                // Micro-animation: briefly open the cart
                openCart();
                setTimeout(closeCart, 1200);
            });
        });
    }

    function renderError(msg) {
        errorSection.classList.remove('hidden');
        errorMessage.textContent = `שגיאה: ${msg}`;
    }

    /* ══════════════════════════════════════════════
       Init
    ══════════════════════════════════════════════ */
    renderCart();   // Restore cart from localStorage on page load
});
