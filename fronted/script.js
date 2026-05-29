// Initialize Socket.io
const socket = io('http://localhost:5000'); // Adjust to your backend URL

// Chart instances
let zoneChart, genderChart, ageChart, trendChart, peakChart, attendanceChart;

// DOM Elements
const zoneStatusElement = document.getElementById('zoneStatus');
const recentNotificationsElement = document.getElementById('recentNotifications');
const totalVisitorsElement = document.getElementById('totalVisitors');
const maxCapacityUsedElement = document.getElementById('maxCapacityUsed');
const activeAlertsElement = document.getElementById('activeAlerts');
const globalAlertElement = document.getElementById('globalAlert');
const alertTitleElement = document.getElementById('alertTitle');
const alertMessageElement = document.getElementById('alertMessage');
const anomalyAlertElement = document.getElementById('anomalyAlert');
const anomalyDetailsElement = document.getElementById('anomalyDetails');
const anomalyListElement = document.getElementById('anomalyList');
const vipAlertElement = document.getElementById('vipAlert');
const vipTitleElement = document.getElementById('vipTitle');
const vipDetailsElement = document.getElementById('vipDetails');
const vipListElement = document.getElementById('vipList');
const iotStatusElement = document.getElementById('iotStatus');

// Initialize charts
function initCharts() {
    // Zone Distribution Chart
    const zoneCtx = document.getElementById('zoneChart').getContext('2d');
    zoneChart = new Chart(zoneCtx, {
        type: 'doughnut',
        data: {
            labels: ['Main Hall', 'Entrance', 'Courtyard', 'Exit'],
            datasets: [{
                data: [0, 0, 0, 0],
                backgroundColor: [
                    '#4caf50',
                    '#ff9800',
                    '#3a6ea5',
                    '#607d8b'
                ]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
    
    // Gender Distribution Chart
    const genderCtx = document.getElementById('genderChart').getContext('2d');
    genderChart = new Chart(genderCtx, {
        type: 'doughnut',
        data: {
            labels: ['Male', 'Female', 'Other'],
            datasets: [{
                data: [0, 0, 0],
                backgroundColor: [
                    '#3a6ea5',
                    '#e91e63',
                    '#9c27b0'
                ]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
    
    // Age Distribution Chart
    const ageCtx = document.getElementById('ageChart').getContext('2d');
    ageChart = new Chart(ageCtx, {
        type: 'bar',
        data: {
            labels: ['0-18', '19-35', '36-50', '51-65', '65+'],
            datasets: [{
                label: 'Visitors',
                data: [0, 0, 0, 0, 0],
                backgroundColor: '#3a6ea5'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
    
    // Real-time Trends Chart
    const trendCtx = document.getElementById('trendChart').getContext('2d');
    trendChart = new Chart(trendCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Total Visitors',
                data: [],
                borderColor: '#3a6ea5',
                tension: 0.3,
                fill: true,
                backgroundColor: 'rgba(58, 110, 165, 0.1)'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
    
    // Peak Times Chart
    const peakCtx = document.getElementById('peakChart').getContext('2d');
    peakChart = new Chart(peakCtx, {
        type: 'bar',
        data: {
            labels: ['6-8 AM', '8-10 AM', '10-12 PM', '12-2 PM', '2-4 PM', '4-6 PM', '6-8 PM'],
            datasets: [{
                label: 'Average Visitors',
                data: [0, 0, 0, 0, 0, 0, 0],
                backgroundColor: '#ff9800'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
    
    // Weekly Attendance Chart
    const attendanceCtx = document.getElementById('attendanceChart').getContext('2d');
    attendanceChart = new Chart(attendanceCtx, {
        type: 'line',
        data: {
            labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
            datasets: [{
                label: 'Total Visitors',
                data: [0, 0, 0, 0, 0, 0, 0],
                borderColor: '#4caf50',
                tension: 0.3,
                fill: true,
                backgroundColor: 'rgba(76, 175, 80, 0.1)'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

// Fetch initial data
async function fetchInitialData() {
    try {
        const crowdResponse = await fetch('http://localhost:5000/api/crowd');
        const crowdData = await crowdResponse.json();
        updateZoneStatus(crowdData);
        updateZoneChart(crowdData);
        updateTotalVisitors(crowdData);
        
        const alertsResponse = await fetch('http://localhost:5000/api/alerts');
        const alertsData = await alertsResponse.json();
        updateActiveAlerts(alertsData);
        updateRecentNotifications(alertsData);
    } catch (error) {
        console.error('Error fetching initial data:', error);
    }
}

// Update zone status
function updateZoneStatus(data) {
    let html = '';
    data.forEach(zone => {
        const percentage = (zone.count / zone.maxCapacity) * 100;
        let statusClass = 'status-normal';
        if (percentage > 90) {
            statusClass = 'status-danger';
        } else if (percentage > 70) {
            statusClass = 'status-warning';
        }
        
        html += `
            <div class="zone-status ${statusClass}">
                <h5>${zone.zone} <span class="badge ${percentage > 90 ? 'bg-danger' : percentage > 70 ? 'bg-warning' : 'bg-success'} float-end">${zone.count}/${zone.maxCapacity}</span></h5>
                <div class="progress mt-2" style="height: 8px;">
                    <div class="progress-bar ${percentage > 90 ? 'bg-danger' : percentage > 70 ? 'bg-warning' : 'bg-success'}" style="width: ${percentage}%"></div>
                </div>
            </div>
        `;
    });
    zoneStatusElement.innerHTML = html;
}

// Update zone chart
function updateZoneChart(data) {
    const zoneData = {
        'Main Prayer Hall': 0,
        'Entrance': 0,
        'Courtyard': 0,
        'Exit Area': 0
    };
    
    data.forEach(zone => {
        zoneData[zone.zone] = zone.count;
    });
    
    zoneChart.data.datasets[0].data = [
        zoneData['Main Prayer Hall'],
        zoneData['Entrance'],
        zoneData['Courtyard'],
        zoneData['Exit Area']
    ];
    zoneChart.update();
}

// Update total visitors
function updateTotalVisitors(data) {
    const total = data.reduce((acc, zone) => acc + zone.count, 0);
    totalVisitorsElement.textContent = total;
    
    const maxCapacity = Math.max(...data.map(zone => (zone.count / zone.maxCapacity) * 100));
    maxCapacityUsedElement.textContent = `${Math.round(maxCapacity)}%`;
}

// Update active alerts
function updateActiveAlerts(data) {
    const activeAlerts = data.filter(alert => alert.severity === 'high').length;
    activeAlertsElement.textContent = activeAlerts;
    document.getElementById('alertCount').textContent = activeAlerts;
}

// Update recent notifications
function updateRecentNotifications(data) {
    let html = '';
    data.slice(0, 4).forEach(alert => {
        const time = new Date(alert.timestamp).toLocaleTimeString();
        html += `
            <div class="notification-item">
                <div class="d-flex justify-content-between">
                    <strong>${alert.message}</strong>
                    <span class="notification-time">${time}</span>
                </div>
                <p class="mb-0">${alert.zone}</p>
            </div>
        `;
    });
    recentNotificationsElement.innerHTML = html;
}

// Socket event listeners
socket.on('crowdUpdate', (data) => {
    // Update the specific zone data
    fetchInitialData(); // For simplicity, we refetch all data
});

socket.on('newAlert', (alert) => {
    // Show global alert if high severity
    if (alert.severity === 'high') {
        alertTitleElement.textContent = alert.message;
        alertMessageElement.textContent = alert.zone;
        globalAlertElement.classList.remove('d-none');
        
        // Play alert sound if enabled
        if (document.getElementById('audioAlerts').checked) {
            playAlertSound();
        }
    }
    
    // Update notifications
    fetchInitialData();
});

// Play alert sound
function playAlertSound() {
    const audio = new Audio('assets/sounds/alert.mp3');
    audio.play();
}

// Initialize everything on load
document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    fetchInitialData();
});