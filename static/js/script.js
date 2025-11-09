// ============================================================================
// REAL-TIME TRAFFIC SIGNAL DASHBOARD - CLIENT SIDE (API VERSION)
// ============================================================================

// Ensure config.js is loaded first
if (typeof API_URL === 'undefined' || typeof API_KEY === 'undefined') {
    console.error('❌ config.js not loaded or API_URL/API_KEY missing');
    alert('Configuration error: Please ensure config.js is loaded before script.js');
}

// API Polling configuration
const API_TIMEOUT_MS = 8000;
const POLL_INTERVAL_MS = 2000;
let pollTimer = null;
let isPolling = false;

// Chart instances
let densityChart, greentimeChart, latencyChart, performanceChart;

// Data storage
const dashboardData = {
    timestamps: [],
    densities: { north: [], south: [], east: [], west: [] },
    greenTimes: { north: [], south: [], east: [], west: [] },
    latencies: []
};

// ============================================================================
// API FETCH WITH TIMEOUT AND ERROR HANDLING
// ============================================================================

async function fetchWithTimeout(url, options = {}, timeout = API_TIMEOUT_MS) {
    const ctrl = new AbortController();
    const id = setTimeout(() => ctrl.abort(), timeout);
    
    try {
        const res = await fetch(url, {
            ...options,
            headers: {
                ...(options.headers || {}),
                'X-API-Key': API_KEY,
                'Content-Type': 'application/json'
            },
            signal: ctrl.signal
        });
        
        if (!res.ok) {
            throw new Error(`HTTP ${res.status}`);
        }
        
        return await res.json();
    } catch (error) {
        if (error.name === 'AbortError') {
            throw new Error('Request timeout');
        }
        throw error;
    } finally {
        clearTimeout(id);
    }
}

// ============================================================================
// API POLLING CONTROL
// ============================================================================

async function fetchStateFromAPI() {
    try {
        const state = await fetchWithTimeout(`${API_URL}/api/state`);
        updateDashboard(state);
        updateMQTTStatus(true);
        document.getElementById('footer-status').textContent = '✓ Connected and receiving data';
        return true;
    } catch (error) {
        console.error('API fetch error:', error);
        updateMQTTStatus(false);
        document.getElementById('footer-status').textContent = '✗ API Error - Retrying...';
        return false;
    }
}

function startPolling() {
    if (isPolling) return;
    isPolling = true;
    
    console.log(`Starting API polling every ${POLL_INTERVAL_MS}ms`);
    fetchStateFromAPI(); // Initial fetch
    pollTimer = setInterval(fetchStateFromAPI, POLL_INTERVAL_MS);
}

function stopPolling() {
    if (!isPolling) return;
    isPolling = false;
    
    if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
    }
    console.log('Stopped API polling');
}

// ============================================================================
// UPDATE DASHBOARD WITH REAL-TIME DATA
// ============================================================================

function updateDashboard(state) {
    // Update densities
    Object.keys(state.densities).forEach(lane => {
        const density = state.densities[lane];
        document.getElementById(`${lane}-density`).textContent = density.toFixed(1);
        dashboardData.densities[lane].push(density);
    });


    // Update green times and signal states
    Object.keys(state.green_times).forEach(lane => {
        const greenTime = state.green_times[lane];
        document.getElementById(`${lane}-green-time`).textContent = greenTime;
        dashboardData.greenTimes[lane].push(greenTime);
        
        // Update signal state
        updateSignal(lane, greenTime);
        
        // Update status badge
        const status = greenTime > 0 ? 'GREEN' : 'RED';
        updateStatusBadge(lane, status);
    });


    // Update metrics
    document.getElementById('cycle-count').textContent = state.cycle_count;
    document.getElementById('latency-value').textContent = state.latency_ms.toFixed(1);
    document.getElementById('messages-received').textContent = state.messages_received;
    document.getElementById('message-loss').textContent = state.messages_lost;


    // Store latency
    if (state.latency_ms > 0) {
        dashboardData.latencies.push(state.latency_ms);
    }


    // Update charts
    updateAllCharts();
}

// ============================================================================
// SIGNAL VISUALIZATION
// ============================================================================

function updateSignal(lane, greenTime) {
    const redLight = document.getElementById(`${lane}-red`);
    const yellowLight = document.getElementById(`${lane}-yellow`);
    const greenLight = document.getElementById(`${lane}-green`);


    // Reset all lights
    redLight.classList.remove('active-red', 'active-yellow', 'active-green');
    yellowLight.classList.remove('active-red', 'active-yellow', 'active-green');
    greenLight.classList.remove('active-red', 'active-yellow', 'active-green');


    // Set appropriate light
    if (greenTime > 0) {
        greenLight.classList.add('active-green');
    } else {
        redLight.classList.add('active-red');
    }
}

function updateStatusBadge(lane, status) {
    const badge = document.getElementById(`${lane}-status`);
    badge.textContent = status;
    badge.className = 'status-badge ' +
        (status === 'GREEN' ? 'green' : status === 'RED' ? 'red' : 'yellow');
}

function updateMQTTStatus(connected) {
    const indicator = document.getElementById('mqtt-status');
    if (connected) {
        indicator.textContent = '🟢 Connected';
        indicator.classList.add('connected');
    } else {
        indicator.textContent = '🔴 Disconnected';
        indicator.classList.remove('connected');
    }
}

// ============================================================================
// CHART INITIALIZATION AND UPDATES
// ============================================================================

function initCharts() {
    // Chart.js defaults
    Chart.defaults.color = '#ecf0f1';
    Chart.defaults.borderColor = '#2a3f5f';
    Chart.defaults.maintainAspectRatio = false;


    // 1. Density Chart
    const densityCtx = document.getElementById('density-chart').getContext('2d');
    densityChart = new Chart(densityCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'North',
                    borderColor: '#e74c3c',
                    backgroundColor: 'rgba(231, 76, 60, 0.1)',
                    data: [],
                    tension: 0.1,
                    fill: true
                },
                {
                    label: 'South',
                    borderColor: '#3498db',
                    backgroundColor: 'rgba(52, 152, 219, 0.1)',
                    data: [],
                    tension: 0.1,
                    fill: true
                },
                {
                    label: 'East',
                    borderColor: '#27ae60',
                    backgroundColor: 'rgba(39, 174, 96, 0.1)',
                    data: [],
                    tension: 0.1,
                    fill: true
                },
                {
                    label: 'West',
                    borderColor: '#f39c12',
                    backgroundColor: 'rgba(243, 156, 18, 0.1)',
                    data: [],
                    tension: 0.1,
                    fill: true
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: { color: '#ecf0f1' }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    ticks: { color: '#ecf0f1' }
                },
                x: {
                    ticks: { color: '#ecf0f1' }
                }
            }
        }
    });


    // 2. Green Time Chart
    const greentimeCtx = document.getElementById('greentime-chart').getContext('2d');
    greentimeChart = new Chart(greentimeCtx, {
        type: 'bar',
        data: {
            labels: ['North', 'South', 'East', 'West'],
            datasets: [
                {
                    label: 'Green Time (s)',
                    backgroundColor: ['#e74c3c', '#3498db', '#27ae60', '#f39c12'],
                    data: [10, 10, 10, 10]
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: 'y',
            plugins: {
                legend: {
                    labels: { color: '#ecf0f1' }
                }
            },
            scales: {
                x: {
                    ticks: { color: '#ecf0f1' },
                    max: 60
                },
                y: {
                    ticks: { color: '#ecf0f1' }
                }
            }
        }
    });


    // 3. Latency Chart
    const latencyCtx = document.getElementById('latency-chart').getContext('2d');
    latencyChart = new Chart(latencyCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Latency (ms)',
                borderColor: '#667eea',
                backgroundColor: 'rgba(102, 126, 234, 0.1)',
                data: [],
                fill: true,
                tension: 0.1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: { color: '#ecf0f1' }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { color: '#ecf0f1' }
                },
                x: {
                    ticks: { color: '#ecf0f1' }
                }
            }
        }
    });


    // 4. Performance Chart
    const performanceCtx = document.getElementById('performance-chart').getContext('2d');
    performanceChart = new Chart(performanceCtx, {
        type: 'doughnut',
        data: {
            labels: ['North', 'South', 'East', 'West'],
            datasets: [{
                data: [0, 0, 0, 0],
                backgroundColor: ['#e74c3c', '#3498db', '#27ae60', '#f39c12']
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: { color: '#ecf0f1' }
                }
            }
        }
    });
}

function updateAllCharts() {
    if (!densityChart) initCharts();


    const maxPoints = 30;


    // Update labels
    const labels = Array.from({length: Math.min(dashboardData.densities.north.length, maxPoints)}, (_, i) => i);


    // Get last maxPoints of data
    const getDensitySlice = (lane) => dashboardData.densities[lane].slice(-maxPoints);
    const getGreenSlice = (lane) => dashboardData.greenTimes[lane].slice(-maxPoints);
    const getLatencySlice = () => dashboardData.latencies.slice(-maxPoints);


    // Update Density Chart
    if (densityChart && densityChart.data) {
        densityChart.data.labels = labels;
        densityChart.data.datasets[0].data = getDensitySlice('north');
        densityChart.data.datasets[1].data = getDensitySlice('south');
        densityChart.data.datasets[2].data = getDensitySlice('east');
        densityChart.data.datasets[3].data = getDensitySlice('west');
        densityChart.update('none');
    }


    // Update Green Time Chart (BAR CHART - show CURRENT values)
    if (greentimeChart && greentimeChart.data) {
        const currentGreen = dashboardData.greenTimes;
        greentimeChart.data.datasets[0].data = [
            currentGreen.north.length > 0 ? currentGreen.north[currentGreen.north.length - 1] : 10,
            currentGreen.south.length > 0 ? currentGreen.south[currentGreen.south.length - 1] : 10,
            currentGreen.east.length > 0 ? currentGreen.east[currentGreen.east.length - 1] : 10,
            currentGreen.west.length > 0 ? currentGreen.west[currentGreen.west.length - 1] : 10
        ];
        greentimeChart.update('none');
    }


    // Update Latency Chart
    if (latencyChart && latencyChart.data) {
        const latencies = getLatencySlice();
        latencyChart.data.labels = Array.from({length: latencies.length}, (_, i) => i);
        latencyChart.data.datasets[0].data = latencies;
        latencyChart.update('none');
    }


    // Update Performance Chart (DOUGHNUT - show average green time per lane)
    if (performanceChart && performanceChart.data) {
        const avgGreen = {
            north: getGreenSlice('north').length > 0 ? getGreenSlice('north').reduce((a,b) => a+b) / getGreenSlice('north').length : 10,
            south: getGreenSlice('south').length > 0 ? getGreenSlice('south').reduce((a,b) => a+b) / getGreenSlice('south').length : 10,
            east: getGreenSlice('east').length > 0 ? getGreenSlice('east').reduce((a,b) => a+b) / getGreenSlice('east').length : 10,
            west: getGreenSlice('west').length > 0 ? getGreenSlice('west').reduce((a,b) => a+b) / getGreenSlice('west').length : 10
        };
        performanceChart.data.datasets[0].data = [avgGreen.north, avgGreen.south, avgGreen.east, avgGreen.west];
        performanceChart.update('none');
    }
}

// ============================================================================
// CONTROL FUNCTIONS
// ============================================================================

function resetGraphs() {
    dashboardData.timestamps = [];
    dashboardData.densities = { north: [], south: [], east: [], west: [] };
    dashboardData.greenTimes = { north: [], south: [], east: [], west: [] };
    dashboardData.latencies = [];


    if (densityChart) densityChart.destroy();
    if (greentimeChart) greentimeChart.destroy();
    if (latencyChart) latencyChart.destroy();
    if (performanceChart) performanceChart.destroy();


    initCharts();
    alert('✓ Graphs reset');
}

function stopSimulation() {
    if (confirm('Stop the simulation?')) {
        stopPolling();
        updateMQTTStatus(false);
        alert('✓ Simulation stopped');
    }
}

// ============================================================================
// INITIALIZATION
// ============================================================================


document.addEventListener('DOMContentLoaded', function() {
    console.log('Dashboard initialized (API mode)');
    initCharts();
    startPolling();
});


// ============================================================================
// TOP BAR & INFO WINDOW LOGIC (PRESERVED FROM ORIGINAL)
// ============================================================================


document.addEventListener('DOMContentLoaded', function() {
    const infoWindow = document.getElementById('info-window');
    const buttons = document.querySelectorAll('.top-control-bar .btn');


    // Map button IDs to display content and colors
    const buttonData = {
        'reset-btn': {
            color: '#3498db',
            bg: 'rgba(52,152,219,0.15)',
            text: 'All graphs have been reset.',
            action: () => resetGraphs()
        },
        'stop-btn': {
            color: '#e74c3c',
            bg: 'rgba(231,76,60,0.15)',
            text: 'Simulator stopped.',
            action: () => stopSimulation()
        },
        'developed-btn': {
            color: '#1abc9c',
            bg: 'rgba(26,188,156,0.15)',
            text: `
                <div class="developer-section">
                    <img src="/static/images/arman.jpg" alt="Arman Ranjan">
                    <div class="developer-details">
                        <strong>Developed By:</strong><br>
                        <strong>Arman Ranjan</strong><br>
                        Reg. No: 23BCE1731
                    </div>
                </div>


                <div class="developer-separator"></div>


                <div class="guided-by-section">
                    <strong>Guided By:</strong>
                    <div class="professor-section">
                        <img src="/static/images/professor.jpg" alt="Professor">
                        <span>Dr. Swaminathan Annadurai</span>
                    </div>
                </div>
            `,
            action: () => {}
        },
        'learn-btn': {
            color: '#f39c12',
            bg: 'rgba(243,156,18,0.15)',
            text: `
                <strong>📘 Book Inspiration</strong><br>
                <em>"Smart Cities: Big Data, Civic Hackers, and the Quest for a New Utopia"</em> by Anthony M. Townsend<br><br>
                "We should not underestimate the benefits of technology that effectively manage traffic 
                flows and energy loads; monitor and proactively react to changing levels in water basins, 
                rivers and ocean fronts; and otherwise make our cities work better. This frees it to serve 
                the needs of the 'autocatalytic city' ... a place where supple adaptive processes are 
                founded on accurate, real-time local intelligence, citydwellers are empowered to respond 
                appropriately to highly dynamic conditions, and emergent urban order is shaped by the 
                feedback of millions of daily choices."<br><br>
                <hr>
                <strong>🎥 Animated Video Explanation</strong><br><br>
                <div class="video-box">
                    <iframe
                        src="https://www.youtube.com/embed/OnjX0O9dPMc?autoplay=1&mute=1"
                        title="Adaptive IoT Traffic Systems"
                        frameborder="0"
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                        allowfullscreen>
                    </iframe>
                </div>
                <br>


                <hr style="border:1px dotted currentColor;">


                <h4>📚 Research Papers & Articles</h4>
                <ul style="text-align:left; display:inline-block; max-width:90%;">
                    <li><b>I. Zrigui et al., "Adaptive Traffic Signal Control Using AI and Distributed Messaging," JATIT, 2025.</b><br>
                        Proposes a real-time urban traffic control system using sensor data, adaptive algorithms, and an MQTT-based messaging infrastructure for efficient, scalable communication between modules.<br>
                        <a href="http://www.jatit.org/volumes/Vol103No8/35Vol103No8.pdf" target="_blank">[Read PDF]</a>
                    </li><br>
                    <li><b>U. K. Lilhore et al., "Design and Implementation of an ML and IoT Based Adaptive Traffic-management System," 2022.</b><br>
                        Presents an IoT-powered adaptive traffic system using machine learning for dynamic signal control, supporting real-time responses to traffic conditions.<br>
                        <a href="https://pmc.ncbi.nlm.nih.gov/articles/PMC9024789/" target="_blank">[Read article]</a>
                    </li><br>
                    <li><b>A. Agarwal et al., "Fusing crowdsourced data to an adaptive wireless traffic signal control architecture," Elsevier, 2024.</b><br>
                        Discusses how wireless protocols and distributed sensor networks can feed adaptive traffic controllers to optimize flows in real time.<br>
                        <a href="https://www.sciencedirect.com/science/article/abs/pii/S2542660524001100" target="_blank">[Read abstract]</a>
                    </li><br>
                    <li><b>M. Saleem et al., "Smart cities: Fusion-based intelligent traffic congestion control system for vehicular networks," ScienceDirect, 2022.</b><br>
                        Describes ML-powered smart city traffic systems that use dense, real-time sensor inputs for congestion mitigation and route optimization.<br>
                        <a href="https://www.sciencedirect.com/science/article/pii/S111086652200024X" target="_blank">[Read article]</a>
                    </li><br>
                    <li><b>Anthony M. Townsend, "Smart Cities: Big Data, Civic Hackers, and the Quest for a New Utopia," 2013.</b><br>
                        A foundational book on real-time adaptive city infrastructure and the transformative power of connected, sensor-driven feedback systems.<br>
                        <a href="https://ssir.org/books/excerpts/entry/smart_cities_big_data_civic_hackers_and_the_quest_for_a_new_utopia" target="_blank">[More info]</a>
                    </li><br>
                </ul>


                <hr style="border:1px dotted currentColor;">


                <h4>🧩 Practical and Technical Sources</h4>
                <ul style="text-align:left; display:inline-block; max-width:90%;">
                    <li><b>Eclipse Mosquitto Documentation</b><br>
                        Official Guide to open-source MQTT Broker Technology (used as the backbone for project messaging).<br>
                        <a href="https://mosquitto.org/documentation/" target="_blank">[Mosquitto Docs]</a>
                    </li><br>
                    <li><b>Flask-SocketIO Documentation</b><br>
                        How to build real-time dashboards that update with backend events using Python (core of your project’s web interface).<br>
                        <a href="https://flask-socketio.readthedocs.io/" target="_blank">[Flask-SocketIO]</a>
                    </li>
                </ul>
            `
        },
        'help-btn': {
            color: '#2ecc71',
            bg: 'rgba(46,204,113,0.15)',
            text: `
            <div class="help-container">
                <h2>💡 Help & Usage Guide</h2>


                <section>
                    <h3>📍 What You See</h3>
                    <ul>
                        <li><b>Live Intersection View:</b> Traffic lights switch per computed schedule.</li>
                        <li><b>Signal Status Table:</b> Per-lane Density (%), Green Time (s), and current state.</li>
                        <li><b>Charts:</b>
                            <ul>
                                <li>Traffic Density Trend — recent densities for all lanes.</li>
                                <li>Green Time Allocation — current green seconds per lane.</li>
                                <li>Protocol Latency — message delay from sensors to dashboard.</li>
                                <li>Lane Performance — average green time share.</li>
                            </ul>
                        </li>
                    </ul>
                </section>


                <hr>


                <section>
                    <h3>🧭 How to Use</h3>
                    <ul>
                        <li>Watch the left panel to see which lane has the green phase now.</li>
                        <li>Use the Signal Status table to compare per-lane densities and timings.</li>
                        <li>Read the Density Trend to spot rising demand on any lane.</li>
                        <li>Check Green Time Allocation to see how time is distributed this cycle.</li>
                        <li>Use the Latency chart to verify network health (stable low ms is good).</li>
                        <li>Lane Performance shows fairness over time; larger slice = more service.</li>
                    </ul>
                </section>


                <hr>


                <h4>⚙️ How This Website Works Behind the Scenes</h4>
                <p style="text-align:left; display:inline-block;">
                    <b>Simulated Sensors:</b><br>
                    In real life, sensors count vehicles. Here, programs act as virtual sensors, generating realistic traffic numbers for North, South, East, and West lanes.<br><br>


                    <b>Central Hub (MQTT Broker):</b><br>
                    Messages from sensors are sent to a digital “broker” — a background system that routes live data between components.<br><br>


                    <b>Controller:</b><br>
                    Acts like an AI traffic officer. It reads densities and allocates green times dynamically to crowded lanes.<br><br>


                    <b>Dashboard Website:</b><br>
                    Listens to both the sensor data and controller responses, visualizing them as live charts and signal states.<br>
                </p>


                <hr style="border:1px dotted currentColor;">


                <h4>🧩 How the Data Is Generated – Technical Explanation</h4>
                <p style="text-align:left; display:inline-block;">
                    The dashboard uses <b>synthetic simulation methods</b> to generate realistic traffic data — a standard approach in IoT systems when hardware or real-time sensors are unavailable.<br><br>


                    <b>Statistical Models and Random Functions:</b><br>
                    Each lane’s traffic density is generated using time-based simulation algorithms. “Peak” hours use higher ranges (60–90%), “off-peak” use lower (10–40%), with Gaussian noise for realism.<br><br>


                    <b>Moving Average and Window Functions:</b><br>
                    Smooths out random spikes, making traffic behavior appear gradual and natural.<br><br>


                    <b>Simulated Sensor Payloads:</b><br>
                    Every few seconds, new JSON data packets are generated with density, queue length, and timestamp, mimicking live IoT sensor output.<br><br>


                    <b>Message Distribution via MQTT:</b><br>
                    These packets are sent to the MQTT broker, which instantly routes them to the controller and dashboard for display.<br><br>


                    <b>Why Use Synthetic Simulation?</b><br>
                    • Controlled, repeatable experiments<br>
                    • No privacy or safety concerns<br>
                    • Realistic variability and test reproducibility<br>
                </p>


                <hr style="border:1px dotted currentColor;">


                <h4>📊 How Data Is Visualized</h4>
                <p style="text-align:left; display:inline-block;">
                    The dashboard plots real-time simulated values using four key charts:<br>
                    • <b>Traffic Density Trend</b> — line chart showing changing congestion.<br>
                    • <b>Green Time Allocation</b> — bar chart showing adaptive timing.<br>
                    • <b>Lane Performance</b> — doughnut chart representing overall fairness.<br>
                    • <b>Protocol Latency</b> — monitors system responsiveness.<br>
                </p>


                <hr style="border:1px dotted currentColor;">


                <h4>🔁 How Data is Retrieved and Sent</h4>
                <p style="text-align:left; display:inline-block;">
                    Every few seconds, the simulated sensors publish fresh traffic data (“North: 62% full!”).<br>
                    The MQTT broker relays it to both the controller and the website.<br><br>
                    The controller calculates new green times and sends them back.<br>
                    The website then updates instantly to reflect both — live density and adaptive timing.<br>
                </p>


                <hr style="border:1px dotted currentColor;">


                <h4>📈 How Data is Displayed in the Graphs</h4>
                <ul style="text-align:left; display:inline-block;">
                    <li><b>Traffic Density Trend:</b> Tracks real-time crowding of each direction using color-coded lines.</li>
                    <li><b>Green Time Allocation:</b> Bar chart showing per-lane green durations for each cycle.</li>
                    <li><b>Lane Performance:</b> Doughnut chart showing overall green-time share per lane.</li>
                    <li><b>Protocol Latency Distribution:</b> Monitors communication delay; low, flat lines mean good network stability.</li>
                </ul>


                <hr style="border:1px dotted currentColor;">


                <h4>🧠 What These Graphs Tell You</h4>
                <p style="text-align:left; display:inline-block;">
                    When traffic density spikes in a lane, the controller grants more green seconds in the next cycle.<br>
                    Over time, the doughnut chart reveals fairness and adaptation between directions.<br>
                    The latency graph verifies that responses are live — confirming the system’s real-time nature.<br>
                </p>


                <hr style="border:1px dotted currentColor;">



                <section>
                    <h3>🛠️ How to Build the Real-Time Traffic Dashboard</h3>
                    <ol>
                        <li><b>Download and Install Required Software</b><br>
                            Download and install Python (from python.org).<br>
                            Download and install Mosquitto MQTT Broker (from mosquitto.org).<br>
                            Ensure both are added to your system PATH during installation.
                        </li>
                        <li><b>Create Your Project Folder</b><br>
                            Make a new folder (e.g., “my-traffic-project”). Inside it, create:<br>
                            <code>config</code>, <code>results</code>, <code>templates</code>, <code>static/css</code>, <code>static/js</code>
                        </li>
                        <li><b>Copy the Project Files</b> — put all .py, HTML, CSS, and JS files in correct folders.</li>
                        <li><b>Install Python Packages</b> — <code>pip install paho-mqtt flask flask-socketio pyyaml matplotlib pandas numpy</code></li>
                        <li><b>Run Mosquitto Broker</b> — <code>cd "C:\\Program Files\\mosquitto"</code> → <code>mosquitto -v</code></li>
                        <li><b>Start Modules</b> — open terminals and run:<br>
                            <code>python dashboard.py</code><br>
                            <code>python edge_controller.py</code><br>
                            <code>python virtual_sensor.py</code>
                        </li>
                        <li><b>View Dashboard</b> — open <code>http://localhost:5000</code> in your browser.</li>
                    </ol>
                </section>
            </div>
            `
        },
        'download-btn': {
            color: '#343a40',
            bg: 'rgba(52,58,64,0.15)',
            text: `
                <strong>⬇️ Download Graphs & Status</strong><br>
                Capturing live charts and current signal data...<br>
                Download will begin automatically.<br><br>
                If not, <a href="#" id="manual-download-link">Click Here!</a>
            `,
            action: async () => {
                const zip = new JSZip();
                let index = 1;


                // Capture all Chart.js canvases
                const chartCanvases = document.querySelectorAll('canvas');
                if (chartCanvases.length === 0) {
                    alert("No charts found to download!");
                    return;
                }


                for (const canvas of chartCanvases) {
                    try {
                        const chartImage = canvas.toDataURL('image/png');
                        const imgData = chartImage.split(',')[1];
                        zip.file(`chart_${index}.png`, imgData, { base64: true });
                        index++;
                    } catch (err) {
                        console.error("Error capturing chart:", err);
                    }
                }


                // Capture the Signal Status Table
                const statusTable = document.querySelector('.status-table');
                if (statusTable) {
                    try {
                        const tableCanvas = await html2canvas(statusTable, {
                            scale: 2,
                            backgroundColor: '#16213e'
                        });
                        const tableImage = tableCanvas.toDataURL('image/png');
                        const imgData = tableImage.split(',')[1];
                        zip.file(`signal_status_table.png`, imgData, { base64: true });
                    } catch (err) {
                        console.error("Error capturing status table:", err);
                    }
                }


                // Add README for context
                const now = new Date();
                const readmeContent = `
        Traffic Signal Dashboard Snapshot
        =================================
        Generated on: ${now.toLocaleString()}


        Includes:
        - All real-time chart images
        - Current Signal Status Table


        Developed By: Arman Ranjan
        Guided By: Dr. Swaminathan Annadurai
                `;
                zip.file("README.txt", readmeContent);


                // Generate and download ZIP
                const zipBlob = await zip.generateAsync({ type: "blob" });
                saveAs(zipBlob, "traffic_dashboard_snapshot.zip");


                // Manual fallback link
                const manualLink = document.getElementById("manual-download-link");
                if (manualLink) {
                    manualLink.addEventListener("click", (e) => {
                        e.preventDefault();
                        saveAs(zipBlob, "traffic_dashboard_snapshot.zip");
                    });
                }
            }
        }
    };


    buttons.forEach(btn => {
        btn.addEventListener('click', function() {
            const data = buttonData[this.id];
            if (!data) return;


            // Execute custom action (if any)
            if (data.action) data.action();


            // Update info window styling
            infoWindow.style.borderLeftColor = data.color;
            infoWindow.style.backgroundColor = data.bg;
            infoWindow.innerHTML = data.text;
        });
    });
});
