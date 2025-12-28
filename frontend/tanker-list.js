// Tanker List Page JavaScript
let currentPage = 0;
let itemsPerPage = 50;
let allTankers = [];
let filteredTankers = [];
let ws = null;
let autoRefreshInterval = null;
const AUTO_REFRESH_INTERVAL = 5000; // 5 seconds

// State variable to track if filters are active
let filtersActive = false;
// Mode state: true = Live Mode, false = Paused Mode
let liveMode = true;

// Status color mapping
const statusColors = {
    'At Source': 'at-source',
    'Loading': 'loading',
    'In Transit': 'in-transit',
    'Delayed': 'delayed',
    'Unloading': 'unloading',
    'Reached Destination': 'reached-destination'
};

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupWebSocket();
    loadTankers();
    setupFilters();
    setupPagination();
    setupItemsPerPageDropdown();
    updateDateRangeConstraints();
    
    // Start auto-refresh (Live Mode by default)
    startAutoRefresh();
    updateModeIndicator();
});

function setupWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/tankers`;
    
    ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
        // WebSocket connected
    };
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'tanker_update' || data.type === 'status_transition') {
            if (!filtersActive) {
                loadTankers();
            }
        }
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };
    
    ws.onclose = () => {
        // WebSocket disconnected, reconnecting
        setTimeout(setupWebSocket, 3000);
    };
}

async function loadTankers(forceReload = false) {
    try {
        if (filtersActive && !forceReload) {
            return;
        }
        
        const response = await fetch(`/api/tankers?limit=1000&offset=0`);
        const data = await response.json();
        
        if (data.success) {
            // Store current filter values before updating
            const currentSearch = document.getElementById('searchInput')?.value || '';
            const currentStatus = document.getElementById('statusFilter')?.value || '';
            const currentDepot = document.getElementById('depotFilter')?.value || '';
            const currentCity = document.getElementById('cityFilter')?.value || '';
            const currentDestination = document.getElementById('destinationFilter')?.value || '';
            const currentDateFrom = document.getElementById('dateFromFilter')?.value || '';
            const currentDateTo = document.getElementById('dateToFilter')?.value || '';
            
            allTankers = data.tankers;
            
            // Update dropdowns first (this will preserve selected values if they exist in new data)
            loadDepots(currentDepot);
            loadCities(currentCity);
            loadDestinations(currentDestination);
            
            // Restore filter values after dropdowns are rebuilt
            if (document.getElementById('searchInput')) document.getElementById('searchInput').value = currentSearch;
            if (document.getElementById('statusFilter')) document.getElementById('statusFilter').value = currentStatus;
            if (document.getElementById('depotFilter') && currentDepot) document.getElementById('depotFilter').value = currentDepot;
            if (document.getElementById('cityFilter') && currentCity) document.getElementById('cityFilter').value = currentCity;
            if (document.getElementById('destinationFilter') && currentDestination) document.getElementById('destinationFilter').value = currentDestination;
            if (document.getElementById('dateFromFilter')) document.getElementById('dateFromFilter').value = currentDateFrom;
            if (document.getElementById('dateToFilter')) document.getElementById('dateToFilter').value = currentDateTo;
            
            updateDateRangeConstraints();
            validateDateRange();
            updateFilterState();
            
            if (filtersActive) {
                applyFilters();
            } else {
                filteredTankers = [...allTankers];
                renderTankers();
            }
        }
    } catch (error) {
        console.error('Error loading tankers:', error);
    }
}

function renderTankers() {
    const tbody = document.getElementById('tankersTableBody');
    const start = currentPage * itemsPerPage;
    const end = start + itemsPerPage;
    const pageTankers = filteredTankers.slice(start, end);
    
    if (pageTankers.length === 0) {
        tbody.innerHTML = '<tr><td colspan="10" style="text-align: center; padding: 40px;">No tankers found</td></tr>';
        return;
    }
    
    tbody.innerHTML = pageTankers.map(tanker => `
        <tr>
            <td><strong>${tanker.tanker_id}</strong></td>
            <td>${tanker.driver_name || 'N/A'}</td>
            <td>
                <span class="status-badge ${statusColors[tanker.current_status] || ''}">
                    ${tanker.current_status.toUpperCase()}
                </span>
            </td>
            <td>${tanker.source_depot || 'N/A'}</td>
            <td>${tanker.destination || 'N/A'}</td>
            <td>${tanker.current_city || 'Unknown'}</td>
            <td>${tanker.oil_volume_liters ? parseFloat(tanker.oil_volume_liters).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2}) : 'N/A'}</td>
            <td>${tanker.avg_speed_kmh ? parseFloat(tanker.avg_speed_kmh).toFixed(0) : 'N/A'}</td>
            <td>${formatDate(tanker.last_update)}</td>
            <td>
                <button class="view-btn" onclick="viewTanker('${tanker.tanker_id}')">View</button>
            </td>
        </tr>
    `).join('');
    
    updatePagination();
}

function updateDateRangeConstraints() {
    const dateFromFilter = document.getElementById('dateFromFilter');
    const dateToFilter = document.getElementById('dateToFilter');
    
    if (dateFromFilter && dateToFilter) {
        const fromDate = dateFromFilter.value;
        
        if (fromDate) {
            // Set the minimum date for To Date to be the From Date
            // Use both setAttribute and direct property assignment for maximum compatibility
            dateToFilter.setAttribute('min', fromDate);
            dateToFilter.min = fromDate;
            
            // If To Date is currently set and is earlier than From Date, clear it
            if (dateToFilter.value && dateToFilter.value < fromDate) {
                dateToFilter.value = '';
            }
        } else {
            // If From Date is cleared, remove the min restriction
            dateToFilter.removeAttribute('min');
            dateToFilter.min = '';
        }
    }
}

function validateDateRange() {
    const dateFromFilter = document.getElementById('dateFromFilter');
    const dateToFilter = document.getElementById('dateToFilter');
    
    if (dateFromFilter && dateToFilter) {
        const fromDate = dateFromFilter.value;
        const toDate = dateToFilter.value;
        
        // If both dates are set and To Date is earlier than From Date, clear To Date
        if (fromDate && toDate && toDate < fromDate) {
            dateToFilter.value = '';
        }
        
        // Ensure min constraint is always applied when From Date exists
        if (fromDate) {
            dateToFilter.setAttribute('min', fromDate);
        } else {
            dateToFilter.removeAttribute('min');
        }
    }
}

function areFiltersActive() {
    const searchTerm = document.getElementById('searchInput')?.value.trim() || '';
    const statusFilter = document.getElementById('statusFilter')?.value || '';
    const depotFilter = document.getElementById('depotFilter')?.value || '';
    const cityFilter = document.getElementById('cityFilter')?.value || '';
    const destinationFilter = document.getElementById('destinationFilter')?.value || '';
    const dateFromFilter = document.getElementById('dateFromFilter')?.value || '';
    const dateToFilter = document.getElementById('dateToFilter')?.value || '';
    
    // Check if any filter has a value
    return !!(searchTerm || statusFilter || depotFilter || cityFilter || destinationFilter || dateFromFilter || dateToFilter);
}

function updateFilterState() {
    filtersActive = areFiltersActive();
    
    if (filtersActive) {
        liveMode = false;
        stopAutoRefresh();
        updateModeIndicator();
    } else {
        liveMode = true;
        startAutoRefresh();
        updateModeIndicator();
    }
}

function updateModeIndicator() {
    const modeIndicator = document.getElementById('modeIndicator');
    const resumeLiveBtn = document.getElementById('resumeLiveBtn');
    
    if (modeIndicator) {
        if (liveMode) {
            modeIndicator.textContent = '● LIVE';
            modeIndicator.className = 'mode-indicator live';
        } else {
            modeIndicator.textContent = '⏸ PAUSED';
            modeIndicator.className = 'mode-indicator paused';
        }
    }
    
    if (resumeLiveBtn) {
        resumeLiveBtn.style.display = liveMode ? 'none' : 'block';
    }
}

function resumeLive() {
    clearFilters();
    liveMode = true;
    filtersActive = false;
    startAutoRefresh();
    updateModeIndicator();
}

window.resumeLive = resumeLive;

function setupFilters() {
    const searchInput = document.getElementById('searchInput');
    const statusFilter = document.getElementById('statusFilter');
    const depotFilter = document.getElementById('depotFilter');
    const cityFilter = document.getElementById('cityFilter');
    const destinationFilter = document.getElementById('destinationFilter');
    const dateFromFilter = document.getElementById('dateFromFilter');
    const dateToFilter = document.getElementById('dateToFilter');
    
    // Add clear filters functionality
    const clearFiltersBtn = document.getElementById('clearFilters');
    if (clearFiltersBtn) {
        clearFiltersBtn.addEventListener('click', clearFilters);
    }
    
    searchInput.addEventListener('input', applyFilters);
    statusFilter.addEventListener('change', applyFilters);
    depotFilter.addEventListener('change', applyFilters);
    if (cityFilter) cityFilter.addEventListener('change', applyFilters);
    if (destinationFilter) destinationFilter.addEventListener('change', applyFilters);
    
    if (dateFromFilter && dateToFilter) {
        // Primary event handler for From Date changes
        dateFromFilter.addEventListener('change', () => {
            const fromDateValue = dateFromFilter.value;
            
            if (fromDateValue) {
                // Disable all previous dates in To Date
                dateToFilter.min = fromDateValue;
                dateToFilter.setAttribute('min', fromDateValue);
                
                // If To Date is earlier, reset it
                if (dateToFilter.value && dateToFilter.value < fromDateValue) {
                    dateToFilter.value = '';
                }
            } else {
                // If From Date is cleared, remove restriction
                dateToFilter.removeAttribute('min');
                dateToFilter.min = '';
            }
            
            validateDateRange();
            applyFilters();
        });
        
        // Also listen to input event for real-time updates
        dateFromFilter.addEventListener('input', () => {
            const fromDateValue = dateFromFilter.value;
            
            if (fromDateValue) {
                dateToFilter.min = fromDateValue;
                dateToFilter.setAttribute('min', fromDateValue);
                
                if (dateToFilter.value && dateToFilter.value < fromDateValue) {
                    dateToFilter.value = '';
                }
            } else {
                dateToFilter.removeAttribute('min');
                dateToFilter.min = '';
            }
        });
        
        // Validate when To Date changes
        dateToFilter.addEventListener('change', () => {
            validateDateRange();
            applyFilters();
        });
        
        dateToFilter.addEventListener('input', () => {
            validateDateRange();
        });
    }
    
    // Ensure constraints are applied on initial load
    updateDateRangeConstraints();
}

function applyFilters() {
    if (!allTankers || allTankers.length === 0) {
        filteredTankers = [];
        currentPage = 0;
        renderTankers();
        return;
    }
    
    const searchInput = document.getElementById('searchInput');
    const statusFilterEl = document.getElementById('statusFilter');
    const depotFilterEl = document.getElementById('depotFilter');
    const cityFilterEl = document.getElementById('cityFilter');
    const destinationFilterEl = document.getElementById('destinationFilter');
    const dateFromFilterEl = document.getElementById('dateFromFilter');
    const dateToFilterEl = document.getElementById('dateToFilter');
    
    const searchTerm = searchInput ? searchInput.value.trim().toLowerCase() : '';
    const statusFilter = statusFilterEl ? statusFilterEl.value : '';
    const depotFilter = depotFilterEl ? depotFilterEl.value : '';
    const cityFilter = cityFilterEl ? cityFilterEl.value : '';
    const destinationFilter = destinationFilterEl ? destinationFilterEl.value : '';
    const dateFromFilter = dateFromFilterEl ? dateFromFilterEl.value : '';
    const dateToFilter = dateToFilterEl ? dateToFilterEl.value : '';
    
    const hasFilters = searchTerm || statusFilter || depotFilter || cityFilter || destinationFilter || dateFromFilter || dateToFilter;
    
    if (hasFilters) {
        filteredTankers = allTankers.filter(tanker => {
            let matches = true;
            
            if (matches && searchTerm) {
                const tankerId = (tanker.tanker_id || '').toLowerCase();
                const driverName = (tanker.driver_name || '').toLowerCase();
                const currentCity = (tanker.current_city || '').toLowerCase();
                
                matches = tankerId.includes(searchTerm) || 
                         driverName.includes(searchTerm) || 
                         currentCity.includes(searchTerm);
            }
            
            if (matches && statusFilter) {
                matches = (tanker.current_status || '') === statusFilter;
            }
            
            if (matches && depotFilter) {
                matches = (tanker.source_depot || '') === depotFilter;
            }
            
            if (matches && cityFilter) {
                matches = (tanker.current_city || '') === cityFilter;
            }
            
            if (matches && destinationFilter) {
                matches = (tanker.destination || '') === destinationFilter;
            }
            
            if (matches && (dateFromFilter || dateToFilter)) {
                if (!tanker.last_update) {
                    matches = false;
                } else {
                    try {
                        // Parse tanker date
                        const tankerDate = new Date(tanker.last_update);
                        
                        if (isNaN(tankerDate.getTime())) {
                            matches = false;
                        } else {
                            // Normalize tanker date to start of day (00:00:00) for day-level comparison
                            const tankerDateNormalized = new Date(tankerDate);
                            tankerDateNormalized.setHours(0, 0, 0, 0);
                            
                            // Check from date filter
                            if (dateFromFilter) {
                                const fromDate = new Date(dateFromFilter);
                                fromDate.setHours(0, 0, 0, 0);
                                
                                // Tanker date must be >= from date (same day or later)
                                if (tankerDateNormalized < fromDate) {
                                    matches = false;
                                }
                            }
                            
                            // Check to date filter
                            if (matches && dateToFilter) {
                                const toDate = new Date(dateToFilter);
                                toDate.setHours(0, 0, 0, 0);
                                
                                // Tanker date must be <= to date (same day or earlier)
                                // Compare normalized dates (both at start of day)
                                if (tankerDateNormalized > toDate) {
                                    matches = false;
                                }
                            }
                        }
                    } catch (e) {
                        console.error('Error filtering by date:', e);
                        matches = false;
                    }
                }
            }
            
            return matches;
        });
    } else {
        filteredTankers = [...allTankers];
    }
    
    currentPage = 0;
    renderTankers();
    
    // Update filter state and control auto-refresh
    updateFilterState();
}

function startAutoRefresh() {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
    }
    
    if (!filtersActive) {
        autoRefreshInterval = setInterval(() => {
            if (!filtersActive) {
                loadTankers();
            }
        }, AUTO_REFRESH_INTERVAL);
    }
}

function stopAutoRefresh() {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
    }
}

function clearFilters() {
    const searchInput = document.getElementById('searchInput');
    const statusFilter = document.getElementById('statusFilter');
    const depotFilter = document.getElementById('depotFilter');
    const cityFilter = document.getElementById('cityFilter');
    const destinationFilter = document.getElementById('destinationFilter');
    const dateFromFilter = document.getElementById('dateFromFilter');
    const dateToFilter = document.getElementById('dateToFilter');
    
    if (searchInput) searchInput.value = '';
    if (statusFilter) statusFilter.value = '';
    if (depotFilter) depotFilter.value = '';
    if (cityFilter) cityFilter.value = '';
    if (destinationFilter) destinationFilter.value = '';
    if (dateFromFilter) dateFromFilter.value = '';
    if (dateToFilter) dateToFilter.value = '';
    
    // Reset date constraints after clearing
    updateDateRangeConstraints();
    
    // Re-apply filters (which will now show all data and resume auto-refresh)
    applyFilters();
}

function manualReload() {
    filtersActive = false;
    liveMode = true;
    loadTankers(true);
    updateModeIndicator();
}

function loadDepots(preserveValue = '') {
    const depots = [...new Set(allTankers.map(t => t.source_depot).filter(Boolean))];
    const depotFilter = document.getElementById('depotFilter');
    if (!depotFilter) return;
    
    // Clear existing options except "All Depots"
    depotFilter.innerHTML = '<option value="">All Depots</option>';
    
    depots.sort().forEach(depot => {
        const option = document.createElement('option');
        option.value = depot;
        option.textContent = depot;
        if (preserveValue && depot === preserveValue) {
            option.selected = true;
        }
        depotFilter.appendChild(option);
    });
}

function loadCities(preserveValue = '') {
    const cities = [...new Set(allTankers.map(t => t.current_city).filter(Boolean))];
    const cityFilter = document.getElementById('cityFilter');
    
    if (!cityFilter) return;
    
    // Clear existing options except "All Cities"
    cityFilter.innerHTML = '<option value="">All Cities</option>';
    
    cities.sort().forEach(city => {
        const option = document.createElement('option');
        option.value = city;
        option.textContent = city;
        if (preserveValue && city === preserveValue) {
            option.selected = true;
        }
        cityFilter.appendChild(option);
    });
}

function loadDestinations(preserveValue = '') {
    const destinations = [...new Set(allTankers.map(t => t.destination).filter(Boolean))];
    const destinationFilter = document.getElementById('destinationFilter');
    
    if (!destinationFilter) return;
    
    // Clear existing options except "All Destinations"
    destinationFilter.innerHTML = '<option value="">All Destinations</option>';
    
    destinations.sort().forEach(dest => {
        const option = document.createElement('option');
        option.value = dest;
        option.textContent = dest;
        if (preserveValue && dest === preserveValue) {
            option.selected = true;
        }
        destinationFilter.appendChild(option);
    });
}

function setupPagination() {
    document.getElementById('prevPage').addEventListener('click', () => {
        if (currentPage > 0) {
            currentPage--;
            renderTankers();
        }
    });
    
    document.getElementById('nextPage').addEventListener('click', () => {
        const maxPage = Math.ceil(filteredTankers.length / itemsPerPage) - 1;
        if (currentPage < maxPage) {
            currentPage++;
            renderTankers();
        }
    });
}

function setupItemsPerPageDropdown() {
    const itemsPerPageSelect = document.getElementById('itemsPerPageSelect');
    if (!itemsPerPageSelect) return;
    
    // Set initial value to match current itemsPerPage
    itemsPerPageSelect.value = itemsPerPage.toString();
    
    // Add change event listener
    itemsPerPageSelect.addEventListener('change', (e) => {
        itemsPerPage = parseInt(e.target.value, 10);
        currentPage = 0; // Reset to first page
        renderTankers();
    });
}

function updatePagination() {
    const maxPage = Math.ceil(filteredTankers.length / itemsPerPage) - 1;
    document.getElementById('pageInfo').textContent = `Page ${currentPage + 1} of ${maxPage + 1 || 1}`;
    document.getElementById('prevPage').disabled = currentPage === 0;
    document.getElementById('nextPage').disabled = currentPage >= maxPage;
}

function formatDate(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    // Format: DD/MM/YYYY, HH:MM:SS
    const day = String(date.getDate()).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const year = date.getFullYear();
    const hours = String(date.getHours()).padStart(2, '0');
    const minutes = String(date.getMinutes()).padStart(2, '0');
    const seconds = String(date.getSeconds()).padStart(2, '0');
    return `${day}/${month}/${year}, ${hours}:${minutes}:${seconds}`;
}

function viewTanker(tankerId) {
    window.location.href = `/tanker-details.html?id=${encodeURIComponent(tankerId)}`;
}

// Export table as CSV
function exportTable() {
    const table = document.querySelector('.tankers-table');
    if (!table) return;
    
    let csv = [];
    const rows = table.querySelectorAll('tr');
    
    for (let i = 0; i < rows.length; i++) {
        const row = [];
        const cols = rows[i].querySelectorAll('td, th');
        
        for (let j = 0; j < cols.length; j++) {
            let data = cols[j].innerText.replace(/(\r\n|\n|\r)/gm, '');
            data = data.replace(/"/g, '""');
            row.push('"' + data + '"');
        }
        
        csv.push(row.join(','));
    }
    
    const csvFile = new Blob([csv.join('\n')], { type: 'text/csv' });
    const downloadLink = document.createElement('a');
    downloadLink.download = `tankers_${new Date().toISOString().split('T')[0]}.csv`;
    downloadLink.href = window.URL.createObjectURL(csvFile);
    downloadLink.style.display = 'none';
    document.body.appendChild(downloadLink);
    downloadLink.click();
    document.body.removeChild(downloadLink);
}

// Make functions available globally
window.viewTanker = viewTanker;
window.exportTable = exportTable;

