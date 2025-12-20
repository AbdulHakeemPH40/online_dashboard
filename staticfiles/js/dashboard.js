// Live dashboard search and table rendering
console.log('Dashboard JS loaded: selection modal enabled');

// Helper function for consistent platform detection
function getPlatform() {
    const platform = (window.DASHBOARD_PLATFORM || 'pasons').toLowerCase().trim();
    return (platform === 'talabat') ? 'talabat' : 'pasons';
}

function escapeHtml(str) {
    if (typeof str !== 'string') return str;
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function getCSRFToken() {
    const name = 'csrftoken=';
    const cookies = document.cookie ? document.cookie.split(';') : [];
    for (let i = 0; i < cookies.length; i++) {
        let c = cookies[i].trim();
        if (c.startsWith(name)) {
            return decodeURIComponent(c.substring(name.length));
        }
    }
    return '';
}

function renderProductsTable(items) {
    const tbody = document.getElementById('products-table');
    if (!tbody) return;
    if (!items || items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10" style="padding: 12px; color: #666;">No items found.</td></tr>';
        return;
    }
    const rows = items.map(item => {
        const locations = Array.isArray(item.locations) ? item.locations.join(', ') : (item.locations || '');
        const mrp = typeof item.mrp === 'number' ? item.mrp.toFixed(2) : item.mrp;
        const cost = typeof item.cost === 'number' ? item.cost.toFixed(2) : item.cost;
        return `
        <tr>
            <td class="px-4 md:px-6 py-3" style="font-family: Arial, sans-serif; color: #333;">${escapeHtml(item.description)} (${escapeHtml(item.item_code)})</td>
            <td class="px-4 md:px-6 py-3" style="font-family: Arial, sans-serif; color: #333;">${escapeHtml(item.pack_description || '')}</td>
            <td class="px-4 md:px-6 py-3" style="font-family: Arial, sans-serif; color: #333;">${escapeHtml(locations)}</td>
            <td class="px-4 md:px-6 py-3" style="font-family: Arial, sans-serif; color: #333;">${mrp}</td>
            <td class="px-4 md:px-6 py-3" style="font-family: Arial, sans-serif; color: #333;">${item.stock}</td>
            <td class="px-4 md:px-6 py-3" style="font-family: Arial, sans-serif; color: #333;">${escapeHtml(item.status)}</td>
            <td class="px-4 md:px-6 py-3" style="font-family: Arial, sans-serif; color: #333;">${escapeHtml(item.status_code)}</td>
            <td class="px-4 md:px-6 py-3" style="font-family: Arial, sans-serif; color: #333;">${escapeHtml(item.lock_status || 'N/A')}</td>
            <td class="px-4 md:px-6 py-3" style="font-family: Arial, sans-serif; color: #333;">${cost}</td>
            <td class="px-4 md:px-6 py-3" style="font-family: Arial, sans-serif; color: #333;">—</td>
        </tr>`;
    }).join('');
    tbody.innerHTML = rows;
}

function fetchAndRenderProducts(q) {
    const platform = getPlatform();
    const query = q ? `&q=${encodeURIComponent(q)}` : '';
    fetch(`/integration/api/items/?platform=${platform}${query}&page_size=50&page=1`)
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                renderProductsTable(data.items || []);
            } else {
                console.error('Items load error:', data.message);
                renderProductsTable([]);
            }
        })
        .catch(err => {
            console.error('Fetch error:', err);
            renderProductsTable([]);
        });
}

// Outlet Availability rendering
function clearOutletTable(message) {
    const tbody = document.getElementById('outlet-table');
    if (!tbody) return;
    if (message) {
        tbody.innerHTML = `<tr><td colspan="8" style="padding: 12px; color: #666;">${escapeHtml(message)}</td></tr>`;
    } else {
        tbody.innerHTML = '';
    }
}

function renderOutletAvailability(outlets, product) {
    const tbody = document.getElementById('outlet-table');
    if (!tbody) return;
    if (!Array.isArray(outlets) || outlets.length === 0) {
        clearOutletTable('No outlet data for this item on the selected platform.');
        return;
    }

    const mrp = product && typeof product.mrp === 'number' ? product.mrp.toFixed(2) : (product ? product.mrp : '—');
    const convertedCost = product && typeof product.converted_cost === 'number' ? product.converted_cost.toFixed(2) : (product && typeof product.cost === 'number' ? product.cost.toFixed(2) : (product ? product.cost : '—'));
    
    // Calculate max outlet values
    let maxOutletCost = 0;
    let maxOutletMrp = 0;
    let maxOutletSellingPrice = 0;
    let maxOutletConvertedCost = 0;
    let maxOutletStock = 0;
    let hasAnyOutletEnabled = false;  // Track if ANY outlet is enabled (stock_status)
    if (Array.isArray(outlets) && outlets.length > 0) {
        outlets.forEach(o => {
            if (o.outlet_cost && typeof o.outlet_cost === 'number' && o.outlet_cost > maxOutletCost) {
                maxOutletCost = o.outlet_cost;
            }
            if (o.outlet_mrp && typeof o.outlet_mrp === 'number' && o.outlet_mrp > maxOutletMrp) {
                maxOutletMrp = o.outlet_mrp;
            }
            if (o.outlet_selling_price && typeof o.outlet_selling_price === 'number' && o.outlet_selling_price > maxOutletSellingPrice) {
                maxOutletSellingPrice = o.outlet_selling_price;
            }
            if (o.outlet_converted_cost && typeof o.outlet_converted_cost === 'number' && o.outlet_converted_cost > maxOutletConvertedCost) {
                maxOutletConvertedCost = o.outlet_converted_cost;
            }
            if (o.stock && typeof o.stock === 'number' && o.stock > maxOutletStock) {
                maxOutletStock = o.stock;
            }
            // Check if ANY outlet is enabled (based on stock rules: stock ÷ OCQ ≥ min_qty)
            // Uses 'active' field which is calculated by backend
            if (o.active === true || o.active === 1) {
                hasAnyOutletEnabled = true;
            }
        });
    }
    
    // ALWAYS update form fields with max outlet values (show 0 when no outlets have values)
    const costField = document.querySelector('[name="cost_price"]');
    const convertedCostField = document.querySelector('[name="converted_cost"]');
    const mrpField = document.querySelector('[name="mrp"]');
    const sellingPriceField = document.querySelector('[name="selling_price"]');
    const stockQuantityField = document.querySelector('[name="stock_quantity"]');
    const stockStatusField = document.querySelector('[name="stock_status"]');
    
    // Cost field - always show max or 0
    if (costField) costField.value = maxOutletCost > 0 ? maxOutletCost.toFixed(2) : '0.00';
    
    // Converted Cost - calculate from max cost or use max converted_cost from outlets
    if (convertedCostField) {
        if (maxOutletConvertedCost > 0) {
            convertedCostField.value = maxOutletConvertedCost.toFixed(3);
        } else if (maxOutletCost > 0 && product && product.weight_division_factor && product.weight_division_factor > 0) {
            const calculated = (maxOutletCost / product.weight_division_factor).toFixed(3);
            convertedCostField.value = calculated;
        } else {
            convertedCostField.value = '0.000';
        }
    }
    
    // MRP field - always show max or 0
    if (mrpField) mrpField.value = maxOutletMrp > 0 ? maxOutletMrp.toFixed(2) : '0.00';
    
    // Selling Price field - always show max or 0
    if (sellingPriceField) sellingPriceField.value = maxOutletSellingPrice > 0 ? maxOutletSellingPrice.toFixed(2) : '0.00';
    
    // Stock Quantity - always show max or 0
    if (stockQuantityField) stockQuantityField.value = maxOutletStock > 0 ? maxOutletStock : 0;
    
    // Stock Status: 1 if ANY outlet is enabled (passes stock rules), 0 if all disabled
    if (stockStatusField) {
        stockStatusField.value = hasAnyOutletEnabled ? '1' : '0';
    }
    const rows = outlets.map(o => {
        const price = typeof o.price === 'number' ? o.price.toFixed(2) : (o.price ?? '—');
        // FIXED: Use outlet-specific MRP, not deprecated product.mrp
        const outletMrp = typeof o.outlet_mrp === 'number' ? o.outlet_mrp.toFixed(2) : (o.outlet_mrp ?? '0.00');
        // Outlet-specific selling price (already calculated with margin for Talabat)
        const outletSellingPrice = typeof o.outlet_selling_price === 'number' ? o.outlet_selling_price.toFixed(2) : (o.outlet_selling_price ?? '0.00');
        // Outlet-specific cost (3 decimals for converted cost)
        const outletCost = typeof o.outlet_cost === 'number' ? o.outlet_cost.toFixed(2) : (o.outlet_cost ?? '0.00');
        const outletConvertedCost = typeof o.outlet_converted_cost === 'number' ? o.outlet_converted_cost.toFixed(3) : (o.outlet_converted_cost ?? '0.000');
        const stock = (o.stock ?? '—');
        const isLinked = !!o.associated;
        const status = isLinked ? (o.active ? 'Enabled' : 'Disabled') : 'Not Linked';
        const statusClass = isLinked ? (o.active ? 'badge badge--success' : 'badge badge--danger') : 'badge';
        const basePriceLocked = (Object.prototype.hasOwnProperty.call(o, 'price_locked') ? !!o.price_locked : !!o.locked);
        const baseStatusLocked = (Object.prototype.hasOwnProperty.call(o, 'status_locked') ? !!o.status_locked : false);
        const priceLocked = isLinked ? basePriceLocked : false;
        const statusLocked = isLinked ? baseStatusLocked : false;
        const clsPriceLocked = !!(product && product.price_locked);
        const clsStatusLocked = !!(product && product.status_locked);
        const isPriceDisabled = priceLocked || clsPriceLocked;
        const outletName = `${escapeHtml(o.outlet_name || '')}` + (o.store_id ? ` (${escapeHtml(String(o.store_id))})` : '');
        // Talabat margin display (Talabat-only)
        const platform = getPlatform();
        const marginDisplay = platform === 'talabat' ? (product && product.talabat_margin ? parseFloat(product.talabat_margin).toFixed(2) + '%' : 'Auto') : '';
        return `
        <tr>
            <td class="px-4 md:px-6 py-3 outlet-name" data-label="Outlet">${outletName}</td>
            <td class="px-4 md:px-6 py-3 number-cell cell-muted" data-label="MRP">${outletMrp}</td>
            <td class="px-4 md:px-6 py-3 number-cell" data-label="Stock">${stock}</td>
            <td class="px-4 md:px-6 py-3 number-cell" data-label="Selling Price">
              <span class="outlet-price-display">${price}</span>
              <input type="number" step="0.01" min="0" class="outlet-price-input" 
                     data-store-id="${escapeHtml(String(o.store_id || ''))}" 
                     data-item-code="${escapeHtml(String((product && product.item_code) || ''))}" 
                     data-units="${escapeHtml(String((product && product.units) || ''))}" 
                     value="${price === '—' ? '' : price}" ${isPriceDisabled ? 'disabled' : ''}
                     style="width:110px; padding:4px 6px; border:1px solid #ddd; border-radius:6px; display:none;" 
                     title="Edit selling price and click Save" />
              <button type="button" class="icon-btn price-edit-btn" ${isPriceDisabled ? 'disabled' : ''}
                      title="Edit price"><i class="bi bi-pencil-fill"></i></button>
              <button type="button" class="icon-btn price-save-btn" disabled
                      title="Save price"><i class="bi bi-floppy-fill"></i></button>
            </td>
            <td class="px-4 md:px-6 py-3" data-label="Stock Status"><span class="${statusClass}">${status}</span></td>
            <td class="px-4 md:px-6 py-3 number-cell" data-label="Cost">${outletConvertedCost}</td>
            ${platform === 'talabat' ? `<td class="px-4 md:px-6 py-3 number-cell" data-label="Margin %">${marginDisplay}</td>` : ''}
            <td class="px-4 md:px-6 py-3 lock-cell" style="text-align:center;" data-label="BLS Price">
              <input type="checkbox" class="lock-toggle price-lock-toggle" data-store-id="${escapeHtml(String(o.store_id || ''))}" data-item-code="${escapeHtml(String((product && product.item_code) || ''))}" data-units="${escapeHtml(String((product && product.units) || ''))}" ${priceLocked ? 'checked' : ''} style="width:16px;height:16px;accent-color:#16a34a;" title="Toggle price lock" />
            </td>
            <td class="px-4 md:px-6 py-3 lock-cell" style="text-align:center;" data-label="BLS Status">
              <input type="checkbox" class="lock-toggle status-lock-toggle" data-store-id="${escapeHtml(String(o.store_id || ''))}" data-item-code="${escapeHtml(String((product && product.item_code) || ''))}" data-units="${escapeHtml(String((product && product.units) || ''))}" ${statusLocked ? 'checked' : ''} ${clsStatusLocked ? 'disabled' : ''} style="width:16px;height:16px;accent-color:#16a34a;" title="Lock status (disables outlet)" />
            </td>
        </tr>`;
    }).join('');

    tbody.innerHTML = rows;
    // FIXED: Pass both item_code AND units to handlers for unique identification
    const productUnits = product && product.units ? product.units : '';
    bindLockToggleHandlers(product && product.item_code, productUnits);
    bindPriceEditHandlers(product && product.item_code, productUnits);

    // Show/hide Margin % column header based on platform
    const marginHeader = document.getElementById('margin-header');
    if (marginHeader) {
        marginHeader.style.display = getPlatform() === 'talabat' ? '' : 'none';
    }

    // Stock status is now calculated in renderOutletAvailability above
    // ... existing code ...

    // Reflect CLS Status Lock in BLS UI on initial render
    if (product && product.status_locked) {
        disableBLSStatusUi(true);
    } else {
        disableBLSStatusUi(false);
    }

    // Ensure CLS checkboxes reflect product state on reload
    if (product) {
        const clsStatusEl = document.querySelector('[name="status_locked"]');
        if (clsStatusEl) clsStatusEl.checked = !!product.status_locked;
        const clsPriceEl = document.querySelector('[name="price_locked"]');
        if (clsPriceEl) clsPriceEl.checked = !!product.price_locked;
        // Also disable outlet price editing when CLS Price Lock is active
        disableBLSPriceUi(!!product.price_locked);
    }
}

function bindLockToggleHandlers(itemCode, units) {
    const priceBoxes = document.querySelectorAll('.price-lock-toggle');
    const statusBoxes = document.querySelectorAll('.status-lock-toggle');

    priceBoxes.forEach(cb => {
        cb.addEventListener('change', (e) => {
            const box = e.currentTarget;
            const storeId = box.dataset.storeId;
            const itemUnits = box.dataset.units || units || '';
            const desired = box.checked;
            toggleOutletLock(itemCode, itemUnits, storeId, 'price', desired, box);
        });
    });

    statusBoxes.forEach(cb => {
        cb.addEventListener('change', (e) => {
            const box = e.currentTarget;
            const storeId = box.dataset.storeId;
            const itemUnits = box.dataset.units || units || '';
            const desired = box.checked; // checked => lock (inactive)
            toggleOutletLock(itemCode, itemUnits, storeId, 'status', desired, box);
        });
    });
}

function disableBLSStatusUi(disabled) {
    const boxes = document.querySelectorAll('.status-lock-toggle');
    boxes.forEach(cb => { cb.disabled = !!disabled; });
}

// Disable/enable all outlet price editing controls based on CLS Price Lock
function disableBLSPriceUi(disabled) {
    const rows = document.querySelectorAll('#outlet-table tr');
    rows.forEach(row => {
        // Use data-label attribute instead of hard-coded index for robustness
        const priceCell = row.querySelector('td[data-label="Selling Price"]');
        if (!priceCell) return;
        const input = priceCell.querySelector('.outlet-price-input');
        const display = priceCell.querySelector('.outlet-price-display');
        const editBtn = priceCell.querySelector('.price-edit-btn');
        const saveBtn = priceCell.querySelector('.price-save-btn');

        if (input) input.disabled = !!disabled;
        if (disabled) {
            if (input) input.style.display = 'none';
            if (display) display.style.display = '';
            if (editBtn) editBtn.disabled = true;
            if (saveBtn) saveBtn.disabled = true;
        } else {
            if (editBtn) editBtn.disabled = false;
            if (saveBtn) saveBtn.disabled = true; // stays disabled until editing
        }
    });

    // Also disable outlet-level price lock toggles when CLS price is locked
    const priceBoxes = document.querySelectorAll('.price-lock-toggle');
    priceBoxes.forEach(cb => { cb.disabled = !!disabled; });
}

function cascadeBLSStatusFromCLS(itemCode, lock) {
    // Cascade CLS Status Lock to all outlet status toggles
    const boxes = document.querySelectorAll('.status-lock-toggle');
    boxes.forEach(cb => {
        const storeId = cb.dataset.storeId;
        if (!storeId) return;
        // Only send toggle if state differs to reduce requests
        if (cb.checked !== !!lock && itemCode) {
            toggleOutletLock(itemCode, storeId, 'status', !!lock, cb);
        }
        cb.disabled = !!lock;
    });
}

function toggleClsStatusLock(itemCode, desired, checkboxEl, units) {
    // If no item code (not loaded yet), just update UI disable state
    if (!itemCode) { disableBLSStatusUi(!!desired); return; }
    const formData = new FormData();
    formData.append('item_code', itemCode);
    formData.append('value', desired ? 'lock' : 'unlock');
    formData.append('platform', getPlatform());  // Add platform for correct item lookup
    if (units) formData.append('units', units);  // Add units for unique identification
    const csrftoken = getCSRFToken();
    if (!csrftoken) {
        showModal({ title: 'Security Error', message: 'CSRF token missing. Please refresh the page.', type: 'error' });
        return;
    }
    if (checkboxEl) checkboxEl.disabled = true;

    fetch('/integration/api/cls-lock-toggle/', {
        method: 'POST',
        headers: { 'X-CSRFToken': csrftoken },
        body: formData,
    })
    .then(r => r.json())
    .then(data => {
        if (!data.success) {
            showModal({ title: 'CLS Toggle Failed', message: (data.message || 'CLS toggle failed'), type: 'error' });
            if (checkboxEl) checkboxEl.checked = !desired;
            return;
        }
        // Reflect CLS change in UI: disable BLS status toggles and reload outlets
        disableBLSStatusUi(!!data.status_locked);
        fetchItemOutlets(itemCode);
    })
    .catch(err => {
        console.error('CLS toggle error:', err);
        showModal({ title: 'Network Error', message: 'Error toggling CLS', type: 'error' });
        if (checkboxEl) checkboxEl.checked = !desired;
    })
    .finally(() => {
        if (checkboxEl) checkboxEl.disabled = false;
    });
}

// Toggle CLS Price Lock and cascade to outlet price UI
function toggleClsPriceLock(itemCode, desired, checkboxEl, units) {
    // If no item code (not loaded yet), just update UI disable state
    if (!itemCode) { disableBLSPriceUi(!!desired); return; }

    const formData = new FormData();
    formData.append('item_code', itemCode);
    formData.append('lock_type', 'price');
    formData.append('value', desired ? 'lock' : 'unlock');
    formData.append('platform', getPlatform());  // Add platform for correct item lookup
    if (units) formData.append('units', units);  // Add units for unique identification
    const csrftoken = getCSRFToken();
    if (!csrftoken) {
        showModal({ title: 'Security Error', message: 'CSRF token missing. Please refresh the page.', type: 'error' });
        return;
    }
    if (checkboxEl) checkboxEl.disabled = true;

    fetch('/integration/api/cls-lock-toggle/', {
        method: 'POST',
        headers: { 'X-CSRFToken': csrftoken },
        body: formData,
    })
    .then(r => r.json())
    .then(data => {
        if (!data.success) {
            showModal({ title: 'CLS Price Toggle Failed', message: (data.message || 'CLS Price toggle failed'), type: 'error' });
            if (checkboxEl) checkboxEl.checked = !desired;
            return;
        }
        // Disable/enable outlet price editing based on CLS price state
        disableBLSPriceUi(!!data.price_locked);
        // Refresh outlets to reflect cascaded BLS price locks
        fetchItemOutlets(itemCode);
    })
    .catch(err => {
        console.error('CLS price toggle error:', err);
        showModal({ title: 'Network Error', message: 'Error toggling CLS Price Lock', type: 'error' });
        if (checkboxEl) checkboxEl.checked = !desired;
    })
    .finally(() => {
        if (checkboxEl) checkboxEl.disabled = false;
    });
}

function toggleOutletLock(itemCode, units, storeId, lockType, desired, checkboxEl) {
    if (!itemCode || !storeId) return;
    const formData = new FormData();
    formData.append('item_code', itemCode);
    formData.append('units', units || '');  // FIXED: Pass units for unique item identification
    formData.append('store_id', storeId);
    formData.append('lock_type', lockType);
    formData.append('value', desired ? 'lock' : 'unlock');

    const csrftoken = getCSRFToken();
    if (!csrftoken) {
        showModal({ title: 'Security Error', message: 'CSRF token missing. Please refresh the page.', type: 'error' });
        return;
    }
    const row = checkboxEl.closest('tr');
    checkboxEl.disabled = true;

    fetch('/integration/api/outlet-lock-toggle/', {
        method: 'POST',
        headers: { 'X-CSRFToken': csrftoken },
        body: formData,
    })
    .then(r => r.json())
    .then(data => {
        if (!data.success) {
            showModal({ title: 'Lock Toggle Failed', message: (data.message || 'Lock toggle failed'), type: 'error' });
            checkboxEl.checked = !desired;
            return;
        }
        if (lockType === 'status') {
            const active = !!data.active_in_outlet;
            // Use data-label attribute instead of hard-coded index for robustness
            const statusCell = row ? row.querySelector('td[data-label="Stock Status"]') : null;
            if (statusCell) {
                const badge = statusCell.querySelector('.badge');
                const newText = active ? 'Enabled' : 'Disabled';
                const newClass = active ? 'badge badge--success' : 'badge badge--danger';
                if (badge) {
                    badge.textContent = newText;
                    badge.className = newClass;
                } else {
                    statusCell.innerHTML = `<span class="${newClass}">${newText}</span>`;
                }
            }
            checkboxEl.checked = !active; // locked when inactive
        } else if (lockType === 'price') {
            if (data.message) {
                // optional toast/alert; keep minimal
            // showModal({ title: 'Info', message: (data.message || ''), type: 'info' });
            }
            // Reflect backend-persisted state
            checkboxEl.checked = !!data.price_locked;
            // Disable/enable price input and action buttons accordingly
            // Use data-label attribute instead of hard-coded index for robustness
            const priceCell = row ? row.querySelector('td[data-label="Selling Price"]') : null;
            if (priceCell) {
                const input = priceCell.querySelector('.outlet-price-input');
                const editBtn = priceCell.querySelector('.price-edit-btn');
                const saveBtn = priceCell.querySelector('.price-save-btn');
                const display = priceCell.querySelector('.outlet-price-display');
                const locked = !!data.price_locked;
                if (input) input.disabled = locked;
                if (locked) {
                    // Exit editing mode and disable actions
                    if (input) input.style.display = 'none';
                    if (display) display.style.display = '';
                    if (saveBtn) saveBtn.disabled = true;
                    if (editBtn) editBtn.disabled = true;
                } else {
                    // Re-enable edit button; keep input hidden until edit clicked
                    if (editBtn) editBtn.disabled = false;
                }
            }
        }
    })
    .catch(err => {
        console.error('Lock toggle error:', err);
        showModal({ title: 'Network Error', message: 'Error toggling lock', type: 'error' });
        checkboxEl.checked = !desired;
    })
    .finally(() => {
        checkboxEl.disabled = false;
    });
}

function updateOutletPrice(itemCode, units, storeId, newPrice, inputEl, onDone) {
    if (!itemCode || !storeId) return;
    const val = String(newPrice || '').trim();
    if (val === '') {
        // Revert to previous value if empty
        inputEl.value = inputEl.dataset.prevValue || '';
        if (typeof onDone === 'function') onDone(false, inputEl.value);
        return;
    }
    let parsed = Number(val);
    if (isNaN(parsed) || parsed < 0) {
        showModal({ title: 'Invalid Price', message: 'Please enter a valid non-negative price', type: 'warning' });
        inputEl.value = inputEl.dataset.prevValue || '';
        if (typeof onDone === 'function') onDone(false, inputEl.value);
        return;
    }
    // Normalize to 2 decimals for display; backend will validate
    const normalized = parsed.toFixed(2);
    const platform = getPlatform();
    const formData = new FormData();
    formData.append('item_code', itemCode);
    formData.append('units', units || '');  // FIXED: Pass units for unique item identification
    formData.append('store_id', storeId);
    formData.append('price', normalized);
    formData.append('platform', platform);
    const csrftoken = getCSRFToken();
    if (!csrftoken) {
        showModal({ title: 'Security Error', message: 'CSRF token missing. Please refresh the page.', type: 'error' });
        inputEl.disabled = false;
        return;
    }
    inputEl.disabled = true;

    fetch('/integration/api/outlet-price-update/', {
        method: 'POST',
        headers: { 'X-CSRFToken': csrftoken },
        body: formData,
    })
    .then(r => r.json())
    .then(data => {
        if (!data.success) {
            showModal({ title: 'Price Update Failed', message: (data.message || 'Price update failed'), type: 'error' });
            inputEl.value = inputEl.dataset.prevValue || normalized;
            if (typeof onDone === 'function') onDone(false, inputEl.value);
            return;
        }
        // Persist new value in the control
        inputEl.value = normalized;
        inputEl.dataset.prevValue = normalized;
        if (typeof onDone === 'function') onDone(true, normalized);
    })
    .catch(err => {
        console.error('Price update error:', err);
        showModal({ title: 'Network Error', message: 'Error updating price', type: 'error' });
        inputEl.value = inputEl.dataset.prevValue || normalized;
        if (typeof onDone === 'function') onDone(false, inputEl.value);
    })
    .finally(() => {
        inputEl.disabled = false;
    });
}

function bindPriceEditHandlers(itemCode, units) {
    const rows = document.querySelectorAll('#outlet-table tr');
    rows.forEach(row => {
        // Use data-label attribute instead of hard-coded index for robustness
        const cell = row.querySelector('td[data-label="Selling Price"]');
        if (!cell) return;
        const input = cell.querySelector('.outlet-price-input');
        const display = cell.querySelector('.outlet-price-display');
        const editBtn = cell.querySelector('.price-edit-btn');
        const saveBtn = cell.querySelector('.price-save-btn');
        if (!input || !display || !editBtn || !saveBtn) return;

        input.dataset.prevValue = input.value;
        const storeId = input.dataset.storeId;
        // Get units from element data or function parameter
        const itemUnits = input.dataset.units || units || '';

        const startEditing = () => {
            if (input.disabled) {
                showModal({ title: 'Editing Disabled', message: 'Price is locked or item not linked to this outlet.', type: 'warning' });
                return;
            }
            display.style.display = 'none';
            input.style.display = '';
            saveBtn.disabled = false;
            editBtn.disabled = true;
            input.focus();
            input.select();
        };

        const stopEditing = (enableEdit = true) => {
            input.style.display = 'none';
            display.style.display = '';
            saveBtn.disabled = true;
            // Re-enable edit button unless price is locked (check BLS lock checkbox)
            const priceLockCheckbox = row.querySelector('.price-lock-toggle');
            const isPriceLocked = priceLockCheckbox ? priceLockCheckbox.checked : false;
            editBtn.disabled = isPriceLocked || !enableEdit;
        };

        editBtn.addEventListener('click', startEditing);
        saveBtn.addEventListener('click', () => {
            if (saveBtn.disabled) return;
            updateOutletPrice(itemCode, itemUnits, storeId, input.value, input, (ok, finalVal) => {
                if (ok) {
                    display.textContent = finalVal;
                    stopEditing();
                }
            });
        });
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                if (saveBtn.disabled) return;
                updateOutletPrice(itemCode, itemUnits, storeId, input.value, input, (ok, finalVal) => {
                    if (ok) {
                        display.textContent = finalVal;
                        stopEditing();
                    }
                });
            }
        });
    });
}

function fetchItemOutlets(itemCode, units, sku) {
    if (!itemCode) { clearOutletTable('Search an item to see outlet availability.'); return; }
    const platform = getPlatform();
    // FIXED: Pass item_code, units, AND sku for unique item identification (especially for wrap=9900 items)
    let url = `/integration/api/item-outlets/?platform=${platform}&item_code=${encodeURIComponent(itemCode)}`;
    if (units) {
        url += `&units=${encodeURIComponent(units)}`;
    }
    if (sku) {
        url += `&sku=${encodeURIComponent(sku)}`;
    }
    fetch(url)
        .then(r => r.json())
        .then(data => {
            if (!data.success) {
                console.error('Outlet availability error:', data.message);
                clearOutletTable('Could not load outlet availability.');
                return;
            }
            renderOutletAvailability(data.outlets || [], data.product || {});
        })
        .catch(err => {
            console.error('Outlet availability fetch error:', err);
            clearOutletTable('Failed to load outlet availability.');
        });
}

// Populate Add/Edit Product form from a single item
function populateProductForm(item) {
    const byName = (n) => document.querySelector(`[name="${n}"]`);
    const setVal = (n, v) => { const el = byName(n); if (el) el.value = (v == null ? '' : String(v)); };
    const setCheck = (n, v) => { const el = byName(n); if (el) el.checked = !!v; };

    // Map API response fields to form fields
    const platform = getPlatform();
    setVal('item_code', item.item_code);
    setVal('name', item.description);  // API: description → form: name
    setVal('pack_description', item.pack_description);
    setVal('sku', item.sku);
    setVal('barcode', item.barcode);
    setVal('units', item.units);
    setVal('mrp', item.mrp);
    setVal('cost_price', item.cost);  // API: cost → form: cost_price
    setVal('selling_price', item.selling_price);
    setVal('stock_quantity', item.stock);  // API: stock → form: stock_quantity
    setVal('wrap', item.wrap);
    setVal('weight_division_factor', item.weight_division_factor);
    setVal('outer_case_quantity', item.outer_case_quantity);
    setVal('minimum_qty', item.minimum_qty);
    // Conversion units fields
    setVal('cost_convert_units', item.cost_convert_units || item.convert_units);
    setVal('sell_convert_units', item.sell_convert_units || item.convert_units);
    // Talabat margin (if available)
    setVal('talabat_margin', item.talabat_margin);
    
    // Converted Cost (auto-calculated or from API)
    if (item.converted_cost !== undefined && item.converted_cost !== null) {
        setVal('converted_cost', item.converted_cost);
    } else if (item.cost && item.weight_division_factor && item.weight_division_factor > 0) {
        // Auto-calculate if not provided
        const calculated = (item.cost / item.weight_division_factor).toFixed(2);
        setVal('converted_cost', calculated);
    } else {
        setVal('converted_cost', '');
    }

    setCheck('is_active', item.is_active);
    setCheck('price_locked', item.price_locked);
    setCheck('status_locked', item.status_locked);

    // Auto-detect margin based on wrap type if margin not explicitly set
    if (item && item.wrap && (!item.talabat_margin || item.talabat_margin === '')) {
        autoDetectMargin();
    }
    // FIXED: Pass item_code, units, AND sku for unique item identification
    if (item && item.item_code) {
        fetchItemOutlets(item.item_code, item.units, item.sku);
    } else {
        clearOutletTable('Search an item to see outlet availability.');
    }
}

// Simple modal to let user pick among multiple search results
function showItemsModal(items, onSelect) {
    // Remove any existing modal
    const existing = document.getElementById('search-modal-overlay');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'search-modal-overlay';
    overlay.style.position = 'fixed';
    overlay.style.inset = '0';
    overlay.style.background = 'rgba(0,0,0,0.4)';
    overlay.style.zIndex = '1000';
    overlay.style.display = 'flex';
    overlay.style.alignItems = 'center';
    overlay.style.justifyContent = 'center';

    const modal = document.createElement('div');
    modal.style.background = '#fff';
    modal.style.width = '90%';
    modal.style.maxWidth = '700px';
    modal.style.borderRadius = '10px';
    modal.style.boxShadow = '0 10px 30px rgba(0,0,0,0.2)';
    modal.style.fontFamily = 'Arial, sans-serif';

    const header = document.createElement('div');
    header.style.display = 'flex';
    header.style.alignItems = 'center';
    header.style.justifyContent = 'space-between';
    header.style.padding = '12px 16px';
    header.style.borderBottom = '1px solid #eee';
    const title = document.createElement('div');
    title.textContent = 'Select a Product';
    title.style.fontWeight = '600';
    const closeBtn = document.createElement('button');
    closeBtn.textContent = '×';
    closeBtn.style.border = 'none';
    closeBtn.style.background = 'transparent';
    closeBtn.style.fontSize = '22px';
    closeBtn.style.cursor = 'pointer';
    closeBtn.addEventListener('click', () => overlay.remove());
    header.appendChild(title);
    header.appendChild(closeBtn);

    const list = document.createElement('div');
    list.style.maxHeight = '360px';
    list.style.overflowY = 'auto';
    list.style.padding = '8px 0';

    items.forEach((item) => {
        const row = document.createElement('div');
        row.style.display = 'grid';
        row.style.gridTemplateColumns = '1fr auto';
        row.style.gap = '8px';
        row.style.padding = '10px 16px';
        row.style.borderBottom = '1px solid #f0f0f0';

        const info = document.createElement('div');
        info.innerHTML = `
          <div style="color:#333; font-size:14px;">${escapeHtml(item.description || '')}</div>
          <div style="color:#555; font-size:12px;">Code: ${escapeHtml(item.item_code || '')} · SKU: ${escapeHtml(item.sku || '')}</div>
          <div style="color:#777; font-size:12px;">Pack: ${escapeHtml(item.pack_description || '')}</div>
        `;

        const select = document.createElement('button');
        select.textContent = 'Select';
        select.style.background = '#2563eb';
        select.style.color = '#fff';
        select.style.border = 'none';
        select.style.borderRadius = '6px';
        select.style.padding = '8px 12px';
        select.style.cursor = 'pointer';
        select.addEventListener('click', () => {
            onSelect(item);
            overlay.remove();
        });

        row.appendChild(info);
        row.appendChild(select);
        list.appendChild(row);
    });

    const footer = document.createElement('div');
    footer.style.display = 'flex';
    footer.style.justifyContent = 'flex-end';
    footer.style.gap = '8px';
    footer.style.padding = '12px 16px';
    const cancel = document.createElement('button');
    cancel.textContent = 'Cancel';
    cancel.style.background = '#e5e7eb';
    cancel.style.border = 'none';
    cancel.style.borderRadius = '6px';
    cancel.style.padding = '8px 12px';
    cancel.style.cursor = 'pointer';
    cancel.addEventListener('click', () => overlay.remove());
    footer.appendChild(cancel);

    modal.appendChild(header);
    modal.appendChild(list);
    modal.appendChild(footer);
    overlay.appendChild(modal);
    document.body.appendChild(overlay);
}

// Search API to fill the form; show modal when multiple results
function searchAndPopulateForm(q) {
    const query = (q || '').trim();
    if (!query) { populateProductForm({}); return; }
    const platform = getPlatform();
    fetch(`/integration/api/search-product/?platform=${platform}&q=${encodeURIComponent(query)}`)
        .then(r => r.json())
        .then(data => {
            const items = Array.isArray(data.items) ? data.items : [];
            if (data.success && items.length > 1) {
                showItemsModal(items, (chosen) => populateProductForm(chosen));
            } else if (data.success && items.length === 1) {
                populateProductForm(items[0]);
            } else {
                // no alert; subtle hint by placeholder
                populateProductForm({});
                const input = document.getElementById('search-input');
                if (input) {
                    const oldPh = input.getAttribute('data-old-placeholder') || input.placeholder || '';
                    input.setAttribute('data-old-placeholder', oldPh);
                    input.placeholder = 'No matching product found';
                    setTimeout(() => { input.placeholder = oldPh; }, 2000);
                }
            }
        })
        .catch(err => {
            console.error('Search error:', err);
        });
}

// Ensure legacy handlers call the new logic
window.searchProduct = function () {
    const input = document.getElementById('search-input');
    const q = input ? input.value.trim() : '';
    searchAndPopulateForm(q);
};

function debounce(fn, delay) {
    let t;
    return (...args) => {
        clearTimeout(t);
        t = setTimeout(() => fn(...args), delay);
    };
}

function saveProduct() {
    const form = document.getElementById('product-form');
    const formData = new FormData(form);
    
    // Map form field names to API field names (form names → model fields)
    const fieldMapping = {
        'item_code': 'item_code',
        'name': 'description',              // Form: name → API: description
        'pack_description': 'pack_description',
        'sku': 'sku',
        'barcode': 'barcode',
        'units': 'units',
        'mrp': 'mrp',
        'cost_price': 'cost',              // Form: cost_price → API: cost
        'selling_price': 'selling_price',
        'stock_quantity': 'stock',         // Form: stock_quantity → API: stock
        'wrap': 'wrap',
        'cost_convert_units': 'convert_units',  // Form: cost_convert_units → API: convert_units
        'sell_convert_units': 'convert_units',  // Form: sell_convert_units → API: convert_units
        'talabat_margin': 'talabat_margin',
        'is_active': 'is_active',
        'price_locked': 'price_locked',
        'status_locked': 'status_locked'
    };
    
    // Convert FormData to JSON with proper field mapping
    const jsonData = {};
    for (let [formField, value] of formData.entries()) {
        const apiField = fieldMapping[formField] || formField;
        jsonData[apiField] = value;
    }
    
    // Add platform parameter (required by backend)
    jsonData['platform'] = getPlatform();
    
    // Get CSRF token
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
    if (!csrfToken) {
        showModal({ title: 'Error', message: 'CSRF token missing. Page may have reloaded.', type: 'error' });
        return;
    }
    
    fetch('/integration/api/save-product/', {
        method: 'POST',
        body: JSON.stringify(jsonData),
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showModal({ title: 'Save Successful', message: (data.message || 'Product saved successfully'), type: 'success' });
            // Clear form and refresh
            resetForm();
            fetchAndRenderProducts('');
        } else {
            showModal({ title: 'Save Error', message: ('Error: ' + (data.message || 'Unknown error')), type: 'error' });
        }
    })
    .catch(error => {
        console.error('Save error:', error);
        showModal({ title: 'Save Failed', message: ('Network error: ' + error.message), type: 'error' });
    });
}

function clearSearch() {
    document.getElementById('search-input').value = '';
}

function resetForm() {
    document.getElementById('product-form').reset();
    document.getElementById('search-input').value = '';
}

// Auto-detect Talabat margin based on wrap item type
function autoDetectMargin() {
    const wrapField = document.querySelector('[name="wrap"]');
    const marginField = document.querySelector('[name="talabat_margin"]');
    
    if (!wrapField || !marginField) return;
    
    const wrapValue = wrapField.value.trim();
    
    // Auto-detect based on wrap type
    if (wrapValue === '9900') {
        marginField.value = '17';  // Wrap items: 17% margin
    } else if (wrapValue === '10000') {
        marginField.value = '15';  // Regular items: 15% margin
    }
}

// Auto-detect margin when wrap field changes
function attachMarginAutoDetect() {
    const wrapField = document.querySelector('[name="wrap"]');
    if (wrapField) {
        wrapField.addEventListener('change', autoDetectMargin);
        wrapField.addEventListener('blur', autoDetectMargin);
    }
}

// Event listeners
document.addEventListener('DOMContentLoaded', function() {
    // Proactively detach any legacy event listeners bound by older scripts
    function detachLegacyHandlers() {
        const ids = ['search-input', 'search-btn', 'clear-search', 'reset-form'];
        const replaced = {};
        ids.forEach(id => {
            const el = document.getElementById(id);
            if (el && el.parentNode) {
                const clone = el.cloneNode(true);
                el.parentNode.replaceChild(clone, el);
                replaced[id] = clone;
            }
        });
        return replaced;
    }

    const controls = detachLegacyHandlers();
    const searchInput = controls['search-input'] || document.getElementById('search-input');
    const debouncedSearch = debounce(() => {
        const val = searchInput.value.trim();
        fetchAndRenderProducts(val);
    }, 300);
    // Initial load
    fetchAndRenderProducts('');
    clearOutletTable('Search an item to see outlet availability.');
    
    // Desktop: Enter key
    searchInput.addEventListener('keypress', e => {
        if (e.key === 'Enter') {
            e.preventDefault();
            searchAndPopulateForm(searchInput.value.trim());
        }
    });
    
    // Mobile: Search on input blur (when user taps away)
    searchInput.addEventListener('blur', () => {
        if (searchInput.value.trim()) fetchAndRenderProducts(searchInput.value.trim());
    });
    // Live: input changes
    searchInput.addEventListener('input', debouncedSearch);
    
    // Mobile: Search button (add to template)
    const searchBtn = controls['search-btn'] || document.getElementById('search-btn');
    if (searchBtn) searchBtn.addEventListener('click', () => searchAndPopulateForm(searchInput.value.trim()));
    
    const clearBtn = controls['clear-search'] || document.getElementById('clear-search');
    const resetBtn = controls['reset-form'] || document.getElementById('reset-form');
    
    if (clearBtn) clearBtn.addEventListener('click', () => { clearSearch(); populateProductForm({}); fetchAndRenderProducts(''); });
    if (resetBtn) resetBtn.addEventListener('click', () => { resetForm(); populateProductForm({}); fetchAndRenderProducts(''); });

    // Attach CLS Status Lock handler to cascade to BLS
    const clsStatus = document.querySelector('[name="status_locked"]');
    if (clsStatus) {
        clsStatus.addEventListener('change', () => {
            const itemCodeInput = document.querySelector('[name="item_code"]');
            const itemCode = itemCodeInput ? itemCodeInput.value.trim() : '';
            const unitsInput = document.querySelector('[name="units"]');
            const units = unitsInput ? unitsInput.value.trim() : '';
            // If no item code, only change UI disable state; otherwise also persist to backend
            toggleClsStatusLock(itemCode, clsStatus.checked, clsStatus, units);
        });
    }

    // Attach CLS Price Lock handler to disable outlet price editing
    const clsPrice = document.querySelector('[name="price_locked"]');
    if (clsPrice) {
        clsPrice.addEventListener('change', () => {
            const itemCodeInput = document.querySelector('[name="item_code"]');
            const itemCode = itemCodeInput ? itemCodeInput.value.trim() : '';
            const unitsInput = document.querySelector('[name="units"]');
            const units = unitsInput ? unitsInput.value.trim() : '';
            toggleClsPriceLock(itemCode, clsPrice.checked, clsPrice, units);
        });
    }

    // Attach margin auto-detection on wrap field change
    attachMarginAutoDetect();
});