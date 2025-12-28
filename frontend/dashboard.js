// Dashboard JavaScript
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
    updateDateRangeConstraints();
    
    // Start auto-refresh (Live Mode by default)
    startAutoRefresh();
    updateModeIndicator();
    
    // Load analytics script if available
    if (typeof initializeCharts === 'function') {
        initializeCharts();
    }
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
        
        // Load all tankers for analytics (no pagination needed)
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
            
            applyFilters();
            
            updateStats();
        }
    } catch (error) {
        console.error('Error loading tankers:', error);
    }
}

function updateStats() {
    const dataToUse = filtersActive ? filteredTankers : allTankers;
    const total = dataToUse.length;
    const inTransit = dataToUse.filter(t => t.current_status === 'In Transit').length;
    const delayed = dataToUse.filter(t => t.current_status === 'Delayed').length;
    
    const totalTankersEl = document.getElementById('totalTankers');
    const inTransitEl = document.getElementById('inTransit');
    const delayedEl = document.getElementById('delayed');
    
    if (totalTankersEl) totalTankersEl.textContent = total;
    if (inTransitEl) inTransitEl.textContent = inTransit;
    if (delayedEl) delayedEl.textContent = delayed;
}

// renderTankers function removed - table section removed from dashboard

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
    
    if (dateFromFilter) {
        dateFromFilter.addEventListener('change', () => {
            updateDateRangeConstraints();
            applyFilters();
        });
    }
    
    if (dateToFilter) {
        dateToFilter.addEventListener('change', () => {
            validateDateRange();
            applyFilters();
        });
    }
}

function updateDateRangeConstraints() {
    const dateFromFilter = document.getElementById('dateFromFilter');
    const dateToFilter = document.getElementById('dateToFilter');
    
    if (dateFromFilter && dateToFilter) {
        const fromDate = dateFromFilter.value;
        
        if (fromDate) {
            dateToFilter.min = fromDate;
            
            if (dateToFilter.value && dateToFilter.value < fromDate) {
                dateToFilter.value = '';
            }
        } else {
            dateToFilter.removeAttribute('min');
        }
    }
}

function validateDateRange() {
    const dateFromFilter = document.getElementById('dateFromFilter');
    const dateToFilter = document.getElementById('dateToFilter');
    
    if (dateFromFilter && dateToFilter && dateFromFilter.value && dateToFilter.value) {
        if (dateToFilter.value < dateFromFilter.value) {
            dateToFilter.value = '';
        }
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
    
    // Clear all filter values
    if (searchInput) searchInput.value = '';
    if (statusFilter) statusFilter.value = '';
    if (depotFilter) depotFilter.value = '';
    if (cityFilter) cityFilter.value = '';
    if (destinationFilter) destinationFilter.value = '';
    if (dateFromFilter) dateFromFilter.value = '';
    if (dateToFilter) dateToFilter.value = '';
    
    // Re-apply filters (which will now show all data and resume auto-refresh)
    applyFilters();
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

async function exportDashboard() {
    const dashboardContent = document.querySelector('.dashboard-content');
    if (!dashboardContent) {
        console.error('Dashboard content not found');
        return;
    }

    try {
        const canvas = await html2canvas(dashboardContent, {
            backgroundColor: '#f5f7fa',
            scale: 2,
            logging: false,
            useCORS: true,
            allowTaint: true,
            scrollX: 0,
            scrollY: 0,
            windowWidth: dashboardContent.scrollWidth,
            windowHeight: dashboardContent.scrollHeight
        });

        const url = canvas.toDataURL('image/png');
        const link = document.createElement('a');
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
        link.download = `dashboard-export-${timestamp}.png`;
        link.href = url;
        link.click();
    } catch (error) {
        console.error('Error exporting dashboard:', error);
        alert('Failed to export dashboard. Please try again.');
    }
}

window.resumeLive = resumeLive;
window.exportDashboard = exportDashboard;

function applyFilters() {
    if (!allTankers || allTankers.length === 0) {
        filteredTankers = [];
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
                        const tankerDate = new Date(tanker.last_update);
                        
                        if (isNaN(tankerDate.getTime())) {
                            matches = false;
                        } else {
                            const tankerDateStr = tankerDate.toISOString().split('T')[0];
                            
                            if (dateFromFilter && tankerDateStr < dateFromFilter) {
                                matches = false;
                            }
                            
                            if (matches && dateToFilter && tankerDateStr > dateToFilter) {
                                matches = false;
                            }
                        }
                    } catch (e) {
                        matches = false;
                    }
                }
            }
            
            return matches;
        });
    } else {
        filteredTankers = [...allTankers];
    }
    
    const dataToDisplay = filteredTankers;
    
    if (typeof updateCharts === 'function') {
        updateCharts(dataToDisplay);
    }
    if (typeof updateKPIs === 'function') {
        updateKPIs(dataToDisplay);
    }
    
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

function manualReload() {
    filtersActive = false;
    liveMode = true;
    loadTankers(true);
    updateModeIndicator();
}

async function loadDepots(preserveValue = '') {
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

// Table rendering and pagination functions removed - table section removed from dashboard

