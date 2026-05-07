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

        // Get form values
        const query = document.getElementById('query').value.trim();
        const maxPrice = parseFloat(document.getElementById('maxPrice').value);

        if (!query || isNaN(maxPrice)) {
            alert('Please provide valid query and max price.');
            return;
        }

        // Prepare UI for loading
        setLoadingState(true);

        try {
            // Send POST request using fetch API
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
                throw new Error(errorData.detail || `Server error: ${response.status}`);
            }

            const data = await response.json();
            
            // Handle success
            renderSuccess(data);

        } catch (error) {
            // Handle error
            renderError(error.message);
        } finally {
            // Re-enable button
            setLoadingState(false, true);
        }
    });

    function setLoadingState(isLoading, requestFinished = false) {
        if (isLoading) {
            startBtn.disabled = true;
            startBtn.innerHTML = '<span>Processing...</span>';
            
            // Reset and show status section
            statusSection.classList.remove('hidden');
            resultsSection.classList.add('hidden');
            loadingIndicator.classList.remove('hidden');
            traceList.innerHTML = '';
            productDetails.classList.remove('hidden');
            
            // Clear any previous messages
            successMessage.className = '';
            successMessage.textContent = '';
        } else {
            startBtn.disabled = false;
            startBtn.innerHTML = '<span>Start Automation</span>';
            if (requestFinished) {
                loadingIndicator.classList.add('hidden');
            }
        }
    }

    function renderSuccess(data) {
        statusSection.classList.remove('hidden');
        resultsSection.classList.remove('hidden');

        // Render trace logs if available
        if (data.trace && data.trace.length > 0) {
            traceList.innerHTML = data.trace.map(item => `
                <li class="trace-item">
                    <span class="trace-step">${item.step_name}</span>
                    <span class="trace-time">${item.execution_time ? item.execution_time.toFixed(2) + 's' : '-'}</span>
                </li>
            `).join('');
        } else {
            traceList.innerHTML = '<li class="trace-item"><span class="trace-step">No trace data available</span></li>';
        }

        // Render product data
        successMessage.className = 'success-message';
        successMessage.textContent = 'Automation completed successfully!';
        
        if (data.product) {
            productTitle.textContent = data.product.title || 'Unknown Product';
            productPrice.textContent = data.product.price || '0';
            
            if (data.product.url) {
                productUrl.href = data.product.url;
                productUrl.style.display = 'inline-block';
            } else {
                productUrl.style.display = 'none';
            }
        } else {
            productTitle.textContent = 'No product found within criteria';
            productPrice.textContent = '0';
            productUrl.style.display = 'none';
        }
    }

    function renderError(errorMessage) {
        statusSection.classList.remove('hidden');
        resultsSection.classList.remove('hidden');
        
        // Hide normal details
        productDetails.classList.add('hidden');
        
        // Show error message
        successMessage.className = 'error-message';
        successMessage.textContent = `Error: ${errorMessage}`;
        
        traceList.innerHTML = `
            <li class="trace-item" style="color: var(--error-color)">
                <span class="trace-step">Process failed</span>
            </li>
        `;
    }
});
