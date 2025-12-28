// Power BI-like Analytics Dashboard
let charts = {};
let previousStats = {};

// Chart.js configuration
const chartColors = {
    primary: '#667eea',
    secondary: '#764ba2',
    success: '#51cf66',
    warning: '#ffa94d',
    danger: '#ff6b6b',
    info: '#4dabf7',
    light: '#e0e0e0'
};

const statusChartColors = {
    'At Source': '#e0e0e0',
    'Loading': '#4dabf7',
    'In Transit': '#51cf66',
    'Delayed': '#ff6b6b',
    'Unloading': '#ffa94d',
    'Reached Destination': '#74c0fc'
};

// Initialize charts
function initializeCharts() {
    // Status Distribution Pie Chart
    charts.statusChart = new Chart(document.getElementById('statusChart'), {
        type: 'doughnut',
        data: {
            labels: [],
            datasets: [{
                data: [],
                backgroundColor: Object.values(statusChartColors),
                borderWidth: 2,
                borderColor: '#fff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            aspectRatio: window.innerWidth < 768 ? 1.2 : 1.5,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        padding: window.innerWidth < 768 ? 10 : 15,
                        font: { size: window.innerWidth < 768 ? 10 : 12 },
                        boxWidth: window.innerWidth < 768 ? 12 : 15
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.parsed || 0;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                            return `${label}: ${value} (${percentage}%)`;
                        }
                    }
                }
            }
        }
    });

    // City Distribution Bar Chart
    charts.cityChart = new Chart(document.getElementById('cityChart'), {
        type: 'bar',
        data: {
            labels: [],
            datasets: [{
                label: 'Tankers',
                data: [],
                backgroundColor: chartColors.primary,
                borderRadius: 5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `Tankers: ${context.parsed.y}`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { stepSize: 1 }
                }
            }
        }
    });

    // Destination Distribution Pie Chart
    charts.destinationChart = new Chart(document.getElementById('destinationChart'), {
        type: 'pie',
        data: {
            labels: [],
            datasets: [{
                data: [],
                backgroundColor: [
                    chartColors.primary,
                    chartColors.secondary,
                    chartColors.success,
                    chartColors.warning,
                    chartColors.danger,
                    chartColors.info,
                    '#a78bfa',
                    '#f472b6',
                    '#fb7185',
                    '#60a5fa'
                ],
                borderWidth: 2,
                borderColor: '#fff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            aspectRatio: window.innerWidth < 768 ? 1.2 : 1.5,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        padding: window.innerWidth < 768 ? 8 : 10,
                        font: { size: window.innerWidth < 768 ? 9 : 11 },
                        boxWidth: window.innerWidth < 768 ? 10 : 12
                    }
                }
            }
        }
    });

    // Volume Analysis Bar Chart
    charts.volumeChart = new Chart(document.getElementById('volumeChart'), {
        type: 'bar',
        data: {
            labels: [],
            datasets: [{
                label: 'Avg Volume (L)',
                data: [],
                backgroundColor: chartColors.info,
                borderRadius: 5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            aspectRatio: window.innerWidth < 768 ? 1.5 : 2,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `Avg Volume: ${context.parsed.y.toLocaleString()} L`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return value.toLocaleString() + ' L';
                        }
                    }
                }
            }
        }
    });

    // Status Trends Line Chart
    charts.trendChart = new Chart(document.getElementById('trendChart'), {
        type: 'line',
        data: {
            labels: [],
            datasets: []
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            aspectRatio: window.innerWidth < 768 ? 1.8 : 2.5,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                legend: {
                    position: window.innerWidth < 768 ? 'bottom' : 'top',
                    labels: { 
                        padding: window.innerWidth < 768 ? 8 : 15,
                        font: { size: window.innerWidth < 768 ? 10 : 12 },
                        boxWidth: window.innerWidth < 768 ? 10 : 12
                    }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    stacked: false
                }
            }
        }
    });

    // Delay Analysis Chart
    charts.delayChart = new Chart(document.getElementById('delayChart'), {
        type: 'bar',
        data: {
            labels: [],
            datasets: [{
                label: 'Delayed',
                data: [],
                backgroundColor: chartColors.danger,
                borderRadius: 5
            }, {
                label: 'On Time',
                data: [],
                backgroundColor: chartColors.success,
                borderRadius: 5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            aspectRatio: window.innerWidth < 768 ? 1.5 : 2,
            plugins: {
                legend: { 
                    position: window.innerWidth < 768 ? 'bottom' : 'top',
                    labels: {
                        font: { size: window.innerWidth < 768 ? 10 : 12 }
                    }
                }
            },
            scales: {
                x: { stacked: true },
                y: { 
                    beginAtZero: true,
                    stacked: true
                }
            }
        }
    });

    // Speed Distribution Chart
    charts.speedChart = new Chart(document.getElementById('speedChart'), {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Avg Speed (km/h)',
                data: [],
                borderColor: chartColors.primary,
                backgroundColor: chartColors.primary + '20',
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            aspectRatio: window.innerWidth < 768 ? 1.5 : 2,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `Speed: ${context.parsed.y.toFixed(1)} km/h`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return value + ' km/h';
                        }
                    }
                }
            }
        }
    });
}

// Update all charts with data
function updateCharts(tankers) {
    if (!tankers || tankers.length === 0) return;

    // Status Distribution
    const statusCounts = {};
    tankers.forEach(t => {
        statusCounts[t.current_status] = (statusCounts[t.current_status] || 0) + 1;
    });
    
    charts.statusChart.data.labels = Object.keys(statusCounts);
    charts.statusChart.data.datasets[0].data = Object.values(statusCounts);
    charts.statusChart.update('none');

    // City Distribution
    const cityCounts = {};
    tankers.forEach(t => {
        const city = t.current_city || 'Unknown';
        cityCounts[city] = (cityCounts[city] || 0) + 1;
    });
    
    const sortedCities = Object.entries(cityCounts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 10); // Top 10 cities
    
    charts.cityChart.data.labels = sortedCities.map(c => c[0]);
    charts.cityChart.data.datasets[0].data = sortedCities.map(c => c[1]);
    charts.cityChart.update('none');

    // Destination Distribution
    const destCounts = {};
    tankers.forEach(t => {
        const dest = t.destination || 'Unknown';
        destCounts[dest] = (destCounts[dest] || 0) + 1;
    });
    
    const sortedDests = Object.entries(destCounts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 10);
    
    charts.destinationChart.data.labels = sortedDests.map(d => d[0]);
    charts.destinationChart.data.datasets[0].data = sortedDests.map(d => d[1]);
    charts.destinationChart.update('none');

    // Volume Analysis by Status
    const volumeByStatus = {};
    tankers.forEach(t => {
        if (t.oil_volume_liters) {
            const status = t.current_status;
            if (!volumeByStatus[status]) {
                volumeByStatus[status] = { sum: 0, count: 0 };
            }
            volumeByStatus[status].sum += parseFloat(t.oil_volume_liters);
            volumeByStatus[status].count += 1;
        }
    });
    
    const statuses = Object.keys(volumeByStatus);
    const avgVolumes = statuses.map(s => volumeByStatus[s].sum / volumeByStatus[s].count);
    
    charts.volumeChart.data.labels = statuses;
    charts.volumeChart.data.datasets[0].data = avgVolumes;
    charts.volumeChart.update('none');

    // Status Trends (simulated time series)
    const now = new Date();
    const labels = [];
    for (let i = 6; i >= 0; i--) {
        const date = new Date(now);
        date.setHours(date.getHours() - i);
        labels.push(date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }));
    }
    
    const statusesForTrend = ['In Transit', 'Delayed', 'At Source', 'Loading'];
    const datasets = statusesForTrend.map((status, idx) => {
        const color = Object.values(statusChartColors)[idx] || chartColors.primary;
        return {
            label: status,
            data: labels.map(() => Math.floor(Math.random() * 20) + 5), // Simulated data
            borderColor: color,
            backgroundColor: color + '20',
            fill: false,
            tension: 0.4
        };
    });
    
    charts.trendChart.data.labels = labels;
    charts.trendChart.data.datasets = datasets;
    charts.trendChart.update('none');

    // Delay Analysis by City
    const delayByCity = {};
    tankers.forEach(t => {
        const city = t.current_city || 'Unknown';
        if (!delayByCity[city]) {
            delayByCity[city] = { delayed: 0, onTime: 0 };
        }
        if (t.current_status === 'Delayed') {
            delayByCity[city].delayed += 1;
        } else {
            delayByCity[city].onTime += 1;
        }
    });
    
    const topCities = Object.entries(delayByCity)
        .sort((a, b) => (b[1].delayed + b[1].onTime) - (a[1].delayed + a[1].onTime))
        .slice(0, 8);
    
    charts.delayChart.data.labels = topCities.map(c => c[0]);
    charts.delayChart.data.datasets[0].data = topCities.map(c => c[1].delayed);
    charts.delayChart.data.datasets[1].data = topCities.map(c => c[1].onTime);
    charts.delayChart.update('none');

    // Speed Distribution by City
    const speedByCity = {};
    tankers.forEach(t => {
        if (t.avg_speed_kmh) {
            const city = t.current_city || 'Unknown';
            if (!speedByCity[city]) {
                speedByCity[city] = { sum: 0, count: 0 };
            }
            speedByCity[city].sum += parseFloat(t.avg_speed_kmh);
            speedByCity[city].count += 1;
        }
    });
    
    const speedCities = Object.entries(speedByCity)
        .sort((a, b) => b[1].count - a[1].count)
        .slice(0, 8)
        .map(c => c[0]);
    const avgSpeeds = speedCities.map(city => 
        speedByCity[city].sum / speedByCity[city].count
    );
    
    charts.speedChart.data.labels = speedCities;
    charts.speedChart.data.datasets[0].data = avgSpeeds;
    charts.speedChart.update('none');
}

// Update KPI cards
function updateKPIs(tankers) {
    if (!tankers || tankers.length === 0) return;

    const total = tankers.length;
    const inTransit = tankers.filter(t => t.current_status === 'In Transit').length;
    const delayed = tankers.filter(t => t.current_status === 'Delayed').length;
    
    // Calculate average volume
    const volumes = tankers
        .filter(t => t.oil_volume_liters)
        .map(t => parseFloat(t.oil_volume_liters));
    const avgVolume = volumes.length > 0 
        ? volumes.reduce((a, b) => a + b, 0) / volumes.length 
        : 0;
    
    // Calculate on-time rate
    const onTimeRate = total > 0 ? ((total - delayed) / total * 100) : 0;

    // Update KPI values
    updateKPIValue('kpiTotal', total, previousStats.total);
    updateKPIValue('kpiInTransit', inTransit, previousStats.inTransit);
    updateKPIValue('kpiDelayed', delayed, previousStats.delayed);
    updateKPIValue('kpiAvgVolume', Math.round(avgVolume).toLocaleString() + ' L', previousStats.avgVolume);
    updateKPIValue('kpiOnTime', onTimeRate.toFixed(1) + '%', previousStats.onTime);

    // Store current stats for next comparison
    previousStats = { total, inTransit, delayed, avgVolume, onTime: onTimeRate };
}

function updateKPIValue(elementId, value, previousValue) {
    const element = document.getElementById(elementId);
    if (element) {
        element.textContent = value;
        
        // Update change indicator
        const changeElement = document.getElementById(elementId + 'Change');
        if (changeElement && previousValue !== undefined) {
            const change = typeof value === 'number' 
                ? value - previousValue 
                : 0;
            if (change > 0) {
                changeElement.textContent = `↑ ${Math.abs(change)}`;
                changeElement.className = 'kpi-change positive';
            } else if (change < 0) {
                changeElement.textContent = `↓ ${Math.abs(change)}`;
                changeElement.className = 'kpi-change negative';
            } else {
                changeElement.textContent = '→';
                changeElement.className = 'kpi-change neutral';
            }
        }
    }
}

// Export chart as image
function exportChart(chartId) {
    const chart = charts[chartId];
    if (chart) {
        const url = chart.toBase64Image();
        const link = document.createElement('a');
        link.download = `${chartId}.png`;
        link.href = url;
        link.click();
    }
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

// Load analytics data
async function loadAnalytics() {
    try {
        const [statsResponse, cityResponse, delayResponse] = await Promise.all([
            fetch('/api/stats'),
            fetch('/api/analytics/by-city'),
            fetch('/api/analytics/delays?days=7')
        ]);
        
        const stats = await statsResponse.json();
        const cityData = await cityResponse.json();
        const delayData = await delayResponse.json();
        
        // Update charts with analytics data if available
        if (cityData.success && cityData.analytics) {
            // Additional city-based visualizations can be added here
        }
        
        if (delayData.success) {
            // Update delay trends if needed
        }
    } catch (error) {
        console.error('Error loading analytics:', error);
    }
}

// Handle window resize for charts
let resizeTimeout;
window.addEventListener('resize', () => {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
        // Update chart aspect ratios on resize
        Object.values(charts).forEach(chart => {
            if (chart && chart.canvas) {
                chart.resize();
            }
        });
    }, 250);
});

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initializeCharts();
    loadAnalytics();
});

