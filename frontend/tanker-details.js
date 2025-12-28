// Tanker Details JavaScript
let map = null;
let marker = null;
let tankerId = null;

// Status color mapping
const statusColors = {
    'At Source': 'at-source',
    'Loading': 'loading',
    'In Transit': 'in-transit',
    'Delayed': 'delayed',
    'Unloading': 'unloading',
    'Reached Destination': 'reached-destination'
};

document.addEventListener('DOMContentLoaded', () => {
    // Tanker Details Page Loaded
    
    // Get tanker ID from URL - check both 'id' and 'tanker_id' parameters
    const urlParams = new URLSearchParams(window.location.search);
    tankerId = urlParams.get('id') || urlParams.get('tanker_id');
    
    // Tanker ID loaded from URL
    
    if (!tankerId) {
        console.error('Tanker ID not found in URL parameters');
        // If no ID provided, show a search/select interface
        showTankerSearch();
        return;
    }
    
    // Loading tanker details
    loadTankerDetails();
    loadTankerHistory();
    loadMLPredictions(tankerId);
    
    // Refresh every 10 seconds
    setInterval(() => {
        loadTankerDetails();
        loadMLPredictions(tankerId);
    }, 10000);
});

function showTankerSearch() {
    const loadingIndicator = document.getElementById('loadingIndicator');
    const detailsContainer = document.getElementById('tankerDetails');
    
    if (loadingIndicator) {
        loadingIndicator.classList.add('hidden');
    }
    
    if (detailsContainer) {
        detailsContainer.innerHTML = `
            <div class="info-card" style="text-align: center; padding: 60px;">
                <h2 style="margin-bottom: 20px;">Select a Tanker</h2>
                <p style="color: #666; margin-bottom: 30px;">Please select a tanker from the dashboard to view its details, or enter a tanker ID below:</p>
                <div style="max-width: 400px; margin: 0 auto;">
                    <input type="text" id="tankerIdInput" placeholder="Enter Tanker ID (e.g., TNK-001)" 
                           style="width: 100%; padding: 12px; border: 2px solid #e0e0e0; border-radius: 8px; font-size: 16px; margin-bottom: 15px; outline: none;">
                    <button onclick="searchTanker()" 
                            style="width: 100%; padding: 12px; background: #667eea; color: white; border: none; border-radius: 8px; font-size: 16px; cursor: pointer; font-weight: 600; transition: background 0.3s;">
                        View Details
                    </button>
                </div>
                <div style="margin-top: 30px;">
                    <a href="/dashboard.html" style="color: #667eea; text-decoration: none; font-weight: 600;">← Back to Dashboard</a>
                </div>
            </div>
        `;
        detailsContainer.classList.remove('hidden');
        
        // Add Enter key listener
        const input = document.getElementById('tankerIdInput');
        if (input) {
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    searchTanker();
                }
            });
            input.focus();
        }
    }
}

function searchTanker() {
    const input = document.getElementById('tankerIdInput');
    if (input && input.value.trim()) {
        window.location.href = `/tanker-details.html?id=${input.value.trim()}`;
    }
}

// Make searchTanker available globally
window.searchTanker = searchTanker;

async function loadTankerDetails() {
    try {
        const response = await fetch(`/api/tankers/${tankerId}`);
        const data = await response.json();
        
        if (data.success && data.tanker) {
            const tanker = data.tanker;
            displayTankerDetails(tanker);
            updateMap(tanker);
        } else {
            alert('Tanker not found');
            window.location.href = '/dashboard.html';
        }
    } catch (error) {
        console.error('Error loading tanker details:', error);
    }
}

function displayTankerDetails(tanker) {
    document.getElementById('tankerTitle').textContent = `Tanker ${tanker.tanker_id}`;
    document.getElementById('tankerId').textContent = tanker.tanker_id;
    document.getElementById('driverName').textContent = tanker.driver_name || 'N/A';
    
    // Status
    const statusBadge = document.getElementById('currentStatus');
    statusBadge.textContent = tanker.current_status;
    statusBadge.className = `status-badge ${statusColors[tanker.current_status] || ''}`;
    
    document.getElementById('sealStatus').textContent = tanker.seal_status || 'N/A';
    document.getElementById('sourceDepot').textContent = tanker.source_depot || 'N/A';
    document.getElementById('destination').textContent = tanker.destination || 'N/A';
    document.getElementById('currentCity').textContent = tanker.current_city || 'Unknown';
    
    // Coordinates
    if (tanker.current_location_lat && tanker.current_location_lon) {
        document.getElementById('coordinates').textContent = 
            `${parseFloat(tanker.current_location_lat).toFixed(6)}, ${parseFloat(tanker.current_location_lon).toFixed(6)}`;
    } else {
        document.getElementById('coordinates').textContent = 'N/A';
    }
    
    // Metrics
    document.getElementById('oilVolume').textContent = 
        tanker.oil_volume_liters ? `${parseFloat(tanker.oil_volume_liters).toLocaleString()} L` : 'N/A';
    document.getElementById('maxCapacity').textContent = 
        tanker.max_capacity_liters ? `${parseFloat(tanker.max_capacity_liters).toLocaleString()} L` : 'N/A';
    document.getElementById('tripDuration').textContent = 
        tanker.trip_duration_hours ? `${parseFloat(tanker.trip_duration_hours).toFixed(2)} hours` : 'N/A';
    document.getElementById('avgSpeed').textContent = 
        tanker.avg_speed_kmh ? `${parseFloat(tanker.avg_speed_kmh).toFixed(0)} km/h` : 'N/A';
    
    // Show details, hide loading
    document.getElementById('loadingIndicator').classList.add('hidden');
    document.getElementById('tankerDetails').classList.remove('hidden');
    
    // Ensure predictions are loaded after content is visible
    if (tankerId) {
        // Loading ML predictions
        loadMLPredictions(tankerId);
    }
}

function updateMap(tanker) {
    if (!tanker.current_location_lat || !tanker.current_location_lon) {
        return;
    }
    
    const lat = parseFloat(tanker.current_location_lat);
    const lon = parseFloat(tanker.current_location_lon);
    
    if (!map) {
        // Initialize map
        map = new google.maps.Map(document.getElementById('map'), {
            center: { lat, lng: lon },
            zoom: 10,
            mapTypeId: 'roadmap'
        });
    } else {
        // Update map center
        map.setCenter({ lat, lng: lon });
    }
    
    // Update or create marker
    if (marker) {
        marker.setPosition({ lat, lng: lon });
    } else {
        marker = new google.maps.Marker({
            position: { lat, lng: lon },
            map: map,
            title: `Tanker ${tanker.tanker_id}`,
            animation: google.maps.Animation.DROP
        });
    }
    
    // Add info window
    const infoWindow = new google.maps.InfoWindow({
        content: `
            <div style="padding: 10px;">
                <h3 style="margin: 0 0 10px 0;">Tanker ${tanker.tanker_id}</h3>
                <p style="margin: 5px 0;"><strong>Status:</strong> ${tanker.current_status}</p>
                <p style="margin: 5px 0;"><strong>City:</strong> ${tanker.current_city || 'Unknown'}</p>
                <p style="margin: 5px 0;"><strong>Driver:</strong> ${tanker.driver_name || 'N/A'}</p>
            </div>
        `
    });
    
    marker.addListener('click', () => {
        infoWindow.open(map, marker);
    });
}

async function loadMLPredictions(tankerId) {
    // Fetching ML predictions
    
    if (!tankerId) {
        console.error('Cannot load predictions: tankerId is not set');
        return;
    }
    
    const arrivalTimeElem = document.getElementById('arrivalTime');
    const delayProbabilityElem = document.getElementById('delayProbability');
    
    if (!arrivalTimeElem || !delayProbabilityElem) {
        console.error('Prediction elements not found in DOM');
        return;
    }
    
    // Show loading state
    arrivalTimeElem.textContent = 'Loading predictions...';
    delayProbabilityElem.textContent = 'Loading predictions...';
    
    try {
        const apiUrl = `/api/tankers/${tankerId}/predictions`;
        // Fetching predictions
        
        const response = await fetch(apiUrl);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        // ML Prediction Response received
        
        if (data.success && data.predictions) {
            const pred = data.predictions;
            
            // Format arrival time as human-readable date/time
            if (pred.arrival_time_hours !== null && pred.arrival_time_hours !== undefined && pred.arrival_time_hours > 0) {
                const now = new Date();
                const arrivalDate = new Date(now.getTime() + (pred.arrival_time_hours * 60 * 60 * 1000));
                const formattedDate = formatArrivalDate(arrivalDate);
                arrivalTimeElem.textContent = formattedDate;
                // Arrival time set
            } else {
                arrivalTimeElem.textContent = 'Not available';
                // Arrival time not available
            }
            
            // Format delay probability as percentage with color coding
            if (pred.delay_probability !== null && pred.delay_probability !== undefined) {
                const probPercent = Math.round(pred.delay_probability * 100);
                delayProbabilityElem.textContent = `${probPercent}%`;
                // Delay probability set
                
                // Color code based on probability thresholds
                delayProbabilityElem.style.color = '';
                delayProbabilityElem.className = 'prediction-value';
                
                if (probPercent < 20) {
                    // Low risk - green
                    delayProbabilityElem.style.color = '#51cf66';
                } else if (probPercent >= 20 && probPercent <= 40) {
                    // Medium risk - orange
                    delayProbabilityElem.style.color = '#ffa94d';
                } else {
                    // High risk - red
                    delayProbabilityElem.style.color = '#ff6b6b';
                }
            } else {
                delayProbabilityElem.textContent = 'Not available';
                delayProbabilityElem.style.color = '';
                // Delay probability not available
            }
        } else {
            // No predictions available
            arrivalTimeElem.textContent = 'Not available';
            delayProbabilityElem.textContent = 'Not available';
            // No predictions in response
        }
    } catch (error) {
        console.error('Error loading predictions:', error);
        arrivalTimeElem.textContent = 'Not available';
        delayProbabilityElem.textContent = 'Not available';
    }
}

// Keep old function name for backward compatibility
async function loadPredictions() {
    if (!tankerId) {
        console.error('loadPredictions called but tankerId is not set');
        return;
    }
    await loadMLPredictions(tankerId);
}

function formatArrivalDate(date) {
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const day = date.getDate();
    const month = months[date.getMonth()];
    const year = date.getFullYear();
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    
    return `${day} ${month} ${year}, ${hours}:${minutes}`;
}

async function loadTankerHistory() {
    try {
        const response = await fetch(`/api/tankers/${tankerId}/history?days=30&limit=50`);
        const data = await response.json();
        
        if (data.success && data.history) {
            displayHistory(data.history);
        }
    } catch (error) {
        console.error('Error loading history:', error);
    }
}

function displayHistory(history) {
    const historyContainer = document.getElementById('statusHistory');
    
    if (history.length === 0) {
        historyContainer.innerHTML = '<p style="color: #666; padding: 20px;">No history available</p>';
        return;
    }
    
    historyContainer.innerHTML = history.map(item => `
        <div class="history-item">
            <div class="history-status">${item.status}</div>
            <div class="history-time">${formatDate(item.recorded_at)}</div>
            ${item.location_lat && item.location_lon ? 
                `<div class="history-location">Location: ${parseFloat(item.location_lat).toFixed(4)}, ${parseFloat(item.location_lon).toFixed(4)}</div>` : 
                ''
            }
        </div>
    `).join('');
}

function formatDate(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleString();
}

