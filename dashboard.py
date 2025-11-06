#!/usr/bin/env python3
"""
Production-Ready Real-Time Traffic Signal Control Dashboard
Flask Web Application with WebSocket Integration
"""

from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit
import paho.mqtt.client as mqtt
import json
import time
import threading
import csv
from collections import deque
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'traffic-control-secret-key-2025'
socketio = SocketIO(app, cors_allowed_origins="*")

# ============================================================================
# GLOBAL DATA STORAGE
# ============================================================================

# Store latest sensor readings (queue of last 60 data points)
sensor_history = {
    'north': deque(maxlen=60),
    'south': deque(maxlen=60),
    'east': deque(maxlen=60),
    'west': deque(maxlen=60)
}

# Current state
current_state = {
    'intersection_id': 'intersection_1',
    'cycle_count': 0,
    'current_cycle': 0,
    'densities': {'north': 0, 'south': 0, 'east': 0, 'west': 0},
    'green_times': {'north': 10, 'south': 10, 'east': 10, 'west': 10},
    'signals': {'north': 'RED', 'south': 'RED', 'east': 'RED', 'west': 'RED'},
    'timestamp': 0,
    'latency_ms': 0,
    'messages_received': 0,
    'messages_lost': 0,
    'avg_wait_time': 0
}

# Metrics for graphs
metrics_log = {
    'timestamps': deque(maxlen=60),
    'north_density': deque(maxlen=60),
    'south_density': deque(maxlen=60),
    'east_density': deque(maxlen=60),
    'west_density': deque(maxlen=60),
    'north_green': deque(maxlen=60),
    'south_green': deque(maxlen=60),
    'east_green': deque(maxlen=60),
    'west_green': deque(maxlen=60),
    'latencies': deque(maxlen=100)
}

# MQTT Client
mqtt_client = mqtt.Client("Dashboard_Server")
mqtt_connected = False

# ============================================================================
# MQTT HANDLERS
# ============================================================================

def on_connect(client, userdata, flags, rc):
    global mqtt_connected
    mqtt_connected = True
    print(f"✓ Dashboard MQTT connected (rc={rc})")

    # Subscribe to all topics
    client.subscribe("traffic/intersection_1/+/density", qos=1)
    client.subscribe("traffic/intersection_1/commands", qos=1)
    client.subscribe("traffic/intersection_1/metrics", qos=1)

def on_message(client, userdata, msg):
    """Handle incoming MQTT messages"""
    try:
        payload = json.loads(msg.payload.decode())

        # Sensor density messages
        if 'density_pct' in payload:
            lane = payload['lane']
            density = payload['density_pct']

            # Update current state
            current_state['densities'][lane] = density
            current_state['messages_received'] += 1

            # Calculate latency
            if 'ts' in payload:
                latency = (time.time() - payload['ts']) * 1000
                current_state['latency_ms'] = round(latency, 2)
                metrics_log['latencies'].append(latency)

            # Store in history
            sensor_history[lane].append({
                'time': time.time(),
                'density': density
            })

        # Controller command messages
        elif 'phase_schedule' in payload:
            current_state['cycle_count'] = payload.get('cycle_count', 0)

            # Extract green times
            schedule = payload.get('phase_schedule', [])
            for phase in schedule:
                lane = phase.get('lane')
                green = phase.get('green', 10)
                current_state['green_times'][lane] = green

            # Update signal states (simplified - in real system would follow timing)
            for lane in current_state['signals']:
                current_state['signals'][lane] = 'GREEN' if current_state['green_times'][lane] > 0 else 'RED'

            # Log metrics
            metrics_log['timestamps'].append(datetime.now().isoformat())
            for lane in ['north', 'south', 'east', 'west']:
                metrics_log[f'{lane}_density'].append(current_state['densities'][lane])
                metrics_log[f'{lane}_green'].append(current_state['green_times'][lane])

        current_state['timestamp'] = time.time()

        # Emit to all connected clients
        socketio.emit('update_state', current_state, to=None)

    except Exception as e:
        print(f"✗ Error processing message: {e}")

def on_disconnect(client, userdata, rc):
    global mqtt_connected
    mqtt_connected = False
    print(f"✗ MQTT disconnected (rc={rc})")

# ============================================================================
# FLASK ROUTES
# ============================================================================

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html', 
                         name='Arman Ranjan',
                         register_no='23BCE1731')

@app.route('/api/state')
def get_state():
    """Get current system state"""
    return jsonify(current_state)

@app.route('/api/history')
def get_history():
    """Get historical metrics"""
    return jsonify({
        'timestamps': list(metrics_log['timestamps']),
        'north': list(metrics_log['north_density']),
        'south': list(metrics_log['south_density']),
        'east': list(metrics_log['east_density']),
        'west': list(metrics_log['west_density']),
        'latencies': {
            'mean': sum(metrics_log['latencies']) / max(1, len(metrics_log['latencies'])),
            'max': max(metrics_log['latencies']) if metrics_log['latencies'] else 0,
            'min': min(metrics_log['latencies']) if metrics_log['latencies'] else 0
        }
    })

@app.route('/api/export')
def export_data():
    """Export metrics to CSV"""
    try:
        filename = f"results/traffic_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'north_density', 'south_density', 'east_density', 'west_density',
                           'north_green', 'south_green', 'east_green', 'west_green'])

            for i in range(len(metrics_log['timestamps'])):
                writer.writerow([
                    metrics_log['timestamps'][i] if i < len(metrics_log['timestamps']) else '',
                    metrics_log['north_density'][i] if i < len(metrics_log['north_density']) else 0,
                    metrics_log['south_density'][i] if i < len(metrics_log['south_density']) else 0,
                    metrics_log['east_density'][i] if i < len(metrics_log['east_density']) else 0,
                    metrics_log['west_density'][i] if i < len(metrics_log['west_density']) else 0,
                    metrics_log['north_green'][i] if i < len(metrics_log['north_green']) else 0,
                    metrics_log['south_green'][i] if i < len(metrics_log['south_green']) else 0,
                    metrics_log['east_green'][i] if i < len(metrics_log['east_green']) else 0,
                    metrics_log['west_green'][i] if i < len(metrics_log['west_green']) else 0
                ])

        return jsonify({'status': 'success', 'file': filename})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

# ============================================================================
# PROJECT DOWNLOAD ROUTE
# ============================================================================
import zipfile
import os

def create_project_zip():
    """Auto-generate project_files.zip excluding unnecessary dirs"""
    zip_path = os.path.join(os.getcwd(), "project_files.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(os.getcwd()):
            if any(ex in root for ex in ["__pycache__", "venv", ".git", "results"]):
                continue
            for file in files:
                if file.endswith(".pyc") or file.endswith(".zip"):
                    continue
                path = os.path.join(root, file)
                arcname = os.path.relpath(path, os.getcwd())
                zipf.write(path, arcname)
    return zip_path


@app.route('/download_project')
def download_project():
    """Provide the project as a .zip file for download"""
    from flask import send_file, jsonify
    try:
        zip_path = create_project_zip()
        return send_file(zip_path, as_attachment=True)
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

# ============================================================================
# SOCKETIO EVENTS
# ============================================================================

@socketio.on('connect')
def handle_connect():
    """Handle WebSocket connection"""
    print("✓ Client connected to dashboard")
    emit('connection_response', {'data': 'Connected to traffic control dashboard'})
    emit('update_state', current_state)

@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnection"""
    print("✗ Client disconnected from dashboard")

@socketio.on('request_state')
def handle_state_request():
    """Handle state request"""
    emit('update_state', current_state)

@socketio.on('request_history')
def handle_history_request():
    """Handle history request"""
    emit('update_history', {
        'timestamps': list(metrics_log['timestamps']),
        'densities': {
            'north': list(metrics_log['north_density']),
            'south': list(metrics_log['south_density']),
            'east': list(metrics_log['east_density']),
            'west': list(metrics_log['west_density'])
        },
        'green_times': {
            'north': list(metrics_log['north_green']),
            'south': list(metrics_log['south_green']),
            'east': list(metrics_log['east_green']),
            'west': list(metrics_log['west_green'])
        }
    })

# ============================================================================
# MQTT CONNECTION THREAD
# ============================================================================

def mqtt_thread():
    """Run MQTT client in separate thread"""
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.on_disconnect = on_disconnect

    try:
        mqtt_client.connect("localhost", 1883, 60)
        mqtt_client.loop_forever()
    except Exception as e:
        print(f"✗ MQTT connection error: {e}")

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    print("\n" + "="*70)
    print("🚦 ADAPTIVE TRAFFIC SIGNAL CONTROL - WEB DASHBOARD")
    print("="*70)
    print("\nStarting MQTT listener thread...")

    # Start MQTT in background
    mqtt_thread_obj = threading.Thread(target=mqtt_thread, daemon=True)
    mqtt_thread_obj.start()

    # Wait for MQTT connection
    time.sleep(2)

    print("\nStarting Flask web server...")
    print("="*70)
    print("\n✓ Dashboard ready!")
    print("\nOpen your browser and go to: http://localhost:5000")
    print("\nMake sure these are running in other terminals:")
    print("  - MQTT Broker (mosquitto)")
    print("  - Edge Controller (edge_controller.py)")
    print("  - Virtual Sensors (virtual_sensor.py)")
    print("\n" + "="*70 + "\n")

    # Run Flask with SocketIO
    socketio.run(app, host='127.0.0.1', port=5000, debug=False)
