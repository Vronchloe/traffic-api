#!/usr/bin/env python3
"""
Complete All-in-One API Backend
Includes: Virtual Sensors + Edge Controller + MQTT + REST API
Designed to run on Render/Railway with GitHub Pages frontend
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import paho.mqtt.client as mqtt
import json
import time
import threading
import os
import random
import math
from collections import deque
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET', 'traffic-control-secret')

# Enable CORS for GitHub Pages
CORS(
    app,
    resources={r"/api/*": {"origins": "*"}},
    allow_headers=["X-API-Key", "Content-Type", "Origin"],
    expose_headers=["Content-Type"],
    methods=["GET", "POST", "OPTIONS"]
)
# ============================================================================
# API KEY SECURITY
# ============================================================================
API_KEY = os.getenv('API_KEY', 'default-api-key-change-me')

def validate_api_key():
    """Validate API key from request headers"""
    key = request.headers.get('X-API-Key')
    if key != API_KEY:
        return False
    return True

# ============================================================================
# GLOBAL STATE
# ============================================================================

current_state = {
    'intersection_id': 'intersection_1',
    'cycle_count': 0,
    'densities': {'north': 0, 'south': 0, 'east': 0, 'west': 0},
    'green_times': {'north': 10, 'south': 10, 'east': 10, 'west': 10},
    'signals': {'north': 'RED', 'south': 'RED', 'east': 'RED', 'west': 'RED'},
    'timestamp': 0,
    'latency_ms': 0,
    'messages_received': 0,
    'messages_lost': 0,
    'api_status': 'running'
}

metrics_log = {
    'timestamps': deque(maxlen=100),
    'north_density': deque(maxlen=100),
    'south_density': deque(maxlen=100),
    'east_density': deque(maxlen=100),
    'west_density': deque(maxlen=100),
    'north_green': deque(maxlen=100),
    'south_green': deque(maxlen=100),
    'east_green': deque(maxlen=100),
    'west_green': deque(maxlen=100),
    'latencies': deque(maxlen=100)
}

sensor_data = {
    'north': deque(maxlen=30),
    'south': deque(maxlen=30),
    'east': deque(maxlen=30),
    'west': deque(maxlen=30)
}

state_lock = threading.Lock()

# ============================================================================
# MQTT SETUP
# ============================================================================

mqtt_client = mqtt.Client("API_Backend_AllInOne")
mqtt_connected = False

def on_mqtt_connect(client, userdata, flags, rc):
    global mqtt_connected
    mqtt_connected = True
    print(f"✓ MQTT Connected (rc={rc})")
    client.subscribe("traffic/intersection_1/+/density", qos=1)
    client.subscribe("traffic/intersection_1/commands", qos=1)

def on_mqtt_message(client, userdata, msg):
    global current_state
    try:
        payload = json.loads(msg.payload.decode())

        with state_lock:
            # Handle sensor density messages
            if 'density_pct' in payload:
                lane = payload.get('lane')
                density = payload.get('density_pct', 0)
                current_state['densities'][lane] = density
                current_state['messages_received'] += 1

                # Calculate latency
                if 'ts' in payload:
                    latency = (time.time() - payload['ts']) * 1000
                    current_state['latency_ms'] = round(latency, 2)
                    metrics_log['latencies'].append(latency)

                # Store for controller algorithm
                sensor_data[lane].append({
                    'density': density,
                    'ts': time.time()
                })

            # Handle controller command messages
            elif 'phase_schedule' in payload:
                current_state['cycle_count'] = payload.get('cycle_count', 0)

                schedule = payload.get('phase_schedule', [])
                for phase in schedule:
                    lane = phase.get('lane')
                    green = phase.get('green', 10)
                    current_state['green_times'][lane] = green
                    current_state['signals'][lane] = 'GREEN' if green > 0 else 'RED'

                # Log metrics
                metrics_log['timestamps'].append(datetime.now().isoformat())
                for lane in ['north', 'south', 'east', 'west']:
                    metrics_log[f'{lane}_density'].append(current_state['densities'][lane])
                    metrics_log[f'{lane}_green'].append(current_state['green_times'][lane])

        current_state['timestamp'] = time.time()

    except Exception as e:
        print(f"✗ MQTT Message Error: {e}")

mqtt_client.on_connect = on_mqtt_connect
mqtt_client.on_message = on_mqtt_message

# ============================================================================
# VIRTUAL SENSOR SIMULATOR
# ============================================================================

class VirtualSensor:
    def __init__(self, lane):
        self.lane = lane
        self.seq = 0
        self.last_density = 50

    def generate_density(self):
        """Generate realistic traffic density"""
        hour = datetime.now().hour

        # Peak hours: 8-10 AM, 5-7 PM
        is_peak = (8 <= hour < 10) or (17 <= hour < 19)

        if is_peak:
            base_density = random.gauss(75, 10)
        else:
            base_density = random.gauss(30, 8)

        # Smooth with moving average
        self.last_density = 0.7 * self.last_density + 0.3 * base_density
        density = max(0, min(100, self.last_density))

        return round(density, 1)

    def publish(self, client):
        """Publish sensor reading to MQTT"""
        density = self.generate_density()
        queue_len = int(density / 10)

        message = {
            'intersection_id': 'intersection_1',
            'lane': self.lane,
            'density_pct': density,
            'queue_len': queue_len,
            'seq': self.seq,
            'ts': time.time()
        }

        topic = f"traffic/intersection_1/{self.lane}/density"
        client.publish(topic, json.dumps(message), qos=1)
        self.seq += 1

# ============================================================================
# ADAPTIVE TRAFFIC CONTROLLER
# ============================================================================

class AdaptiveController:
    def __init__(self):
        self.cycle_count = 0
        self.cycle_length = 60
        self.min_green = 10
        self.max_green = 60
        self.yellow_time = 3
        self.all_red_time = 2
        self.lanes = ['north', 'south', 'east', 'west']

    def compute_green_times(self):
        """Proportional allocation algorithm"""
        # Get average densities
        avg_density = {}
        for lane in self.lanes:
            if sensor_data[lane]:
                avg_density[lane] = sum(d['density'] for d in sensor_data[lane]) / len(sensor_data[lane])
            else:
                avg_density[lane] = 0

        total_density = sum(avg_density.values())

        # Safety: if no traffic
        if total_density <= 0:
            return {lane: self.min_green for lane in self.lanes}

        # Available time for green phases
        available_time = (self.cycle_length - 
                         len(self.lanes) * (self.yellow_time + self.all_red_time))

        # Proportional allocation
        raw_green = {}
        for lane in self.lanes:
            proportion = avg_density[lane] / total_density
            raw_green[lane] = proportion * available_time

        # Apply constraints
        green_times = {}
        for lane in self.lanes:
            green = raw_green[lane]
            green_times[lane] = max(self.min_green, 
                                   min(self.max_green, int(green)))

        # Redistribution
        current_sum = sum(green_times.values())
        diff = available_time - current_sum

        if diff != 0:
            sorted_lanes = sorted(self.lanes, 
                                 key=lambda l: avg_density[l], 
                                 reverse=True)
            for lane in sorted_lanes:
                if diff == 0:
                    break
                adjustment = 1 if diff > 0 else -1
                green_times[lane] += adjustment
                diff -= adjustment

        return green_times

    def publish_schedule(self, client):
        """Publish control schedule to MQTT"""
        green_times = self.compute_green_times()

        phase_schedule = []
        for lane in self.lanes:
            phase_schedule.append({
                'lane': lane,
                'green': green_times[lane],
                'yellow': self.yellow_time
            })

        message = {
            'intersection_id': 'intersection_1',
            'cycle_start_ts': time.time(),
            'cycle_length': self.cycle_length,
            'cycle_count': self.cycle_count,
            'phase_schedule': phase_schedule,
            'algorithm': 'proportional_allocation'
        }

        topic = f"traffic/intersection_1/commands"
        client.publish(topic, json.dumps(message), qos=1)
        self.cycle_count += 1

# ============================================================================
# BACKGROUND THREADS
# ============================================================================

sensors = {lane: VirtualSensor(lane) for lane in ['north', 'south', 'east', 'west']}
controller = AdaptiveController()

def mqtt_thread():
    """MQTT connection thread"""
    mqtt_host = os.getenv('MQTT_HOST', 'localhost')
    mqtt_port = int(os.getenv('MQTT_PORT', 1883))
    try:
        mqtt_client.connect(mqtt_host, mqtt_port, 60)
        mqtt_client.loop_forever()
    except Exception as e:
        print(f"✗ MQTT Error: {e}")

def sensor_thread():
    """Sensor publishing thread"""
    while True:
        try:
            for lane in ['north', 'south', 'east', 'west']:
                sensors[lane].publish(mqtt_client)
            time.sleep(2)  # Publish every 2 seconds
        except Exception as e:
            print(f"✗ Sensor Error: {e}")
            time.sleep(5)

def controller_thread():
    """Controller computation thread"""
    while True:
        try:
            controller.publish_schedule(mqtt_client)
            time.sleep(60)  # Compute every 60 seconds (1 cycle)
        except Exception as e:
            print(f"✗ Controller Error: {e}")
            time.sleep(10)

# ============================================================================
# REST API ENDPOINTS
# ============================================================================
@app.route('/version')
def version():
return {'build': '2025-11-08-1', 'status': 'ok'}

@app.route('/health', methods=['GET'])
def health():
    """Health check (no API key required)"""
    return jsonify({'status': 'ok', 'timestamp': time.time()})

@app.route('/api/state', methods=['GET'])
def get_state():
    """Get current traffic state"""
    if not validate_api_key():
        return jsonify({'error': 'Unauthorized'}), 401

    with state_lock:
        return jsonify(dict(current_state))

@app.route('/api/history', methods=['GET'])
def get_history():
    """Get historical metrics"""
    if not validate_api_key():
        return jsonify({'error': 'Unauthorized'}), 401

    with state_lock:
        return jsonify({
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
            },
            'latencies': {
                'values': list(metrics_log['latencies']),
                'mean': sum(metrics_log['latencies']) / max(1, len(metrics_log['latencies'])),
                'max': max(metrics_log['latencies']) if metrics_log['latencies'] else 0,
                'min': min(metrics_log['latencies']) if metrics_log['latencies'] else 0
            }
        })

@app.route('/api/export', methods=['GET'])
def export_data():
    """Export data as JSON (client converts to CSV if needed)"""
    if not validate_api_key():
        return jsonify({'error': 'Unauthorized'}), 401

    with state_lock:
        return jsonify({
            'exported_at': datetime.now().isoformat(),
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
# MAIN
# ============================================================================

if __name__ == '__main__':
    print("\n" + "="*70)
    print("🚦 ADAPTIVE TRAFFIC CONTROL - PRODUCTION API")
    print("="*70)
    
    # Start background threads (before app starts)
    mqtt_thread_obj = threading.Thread(target=mqtt_thread, daemon=True)
    mqtt_thread_obj.start()
    time.sleep(2)
    
    sensor_thread_obj = threading.Thread(target=sensor_thread, daemon=True)
    sensor_thread_obj.start()
    
    controller_thread_obj = threading.Thread(target=controller_thread, daemon=True)
    controller_thread_obj.start()
    
    print("\n✓ MQTT thread: started")
    print("✓ Sensor simulator: started")
    print("✓ Traffic controller: started")
    print("✓ API Key:", os.getenv('API_KEY', 'NOT SET')[:10] + "...")
    print("✓ MQTT Broker:", os.getenv('MQTT_HOST', 'localhost'))
    print("\n" + "="*70)
    print("✓ PRODUCTION API READY - Listening on all interfaces")
    print("="*70 + "\n")
    
    port = int(os.getenv('PORT', 5000))
    # Use gunicorn in production, but allow direct run for testing
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)
