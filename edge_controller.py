#!/usr/bin/env python3
"""
Adaptive Traffic Signal Controller
Algorithm: Proportional Allocation (NOT Webster's method)
Control: Cycle-based (updates every 60 seconds)
"""

import paho.mqtt.client as mqtt
import yaml
import json
import time
import threading
import csv
from collections import defaultdict
from datetime import datetime

class ProportionalController:
    def __init__(self, config_file='config/controller.yml'):
        # Load configuration
        with open(config_file, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.system = self.config['system']
        self.timing = self.config['timing_parameters']
        self.lanes = self.config['lanes']
        
        # Thread-safe storage for sensor data
        self.lock = threading.Lock()
        self.sensor_data = {lane: [] for lane in self.lanes}
        self.last_seq = {lane: -1 for lane in self.lanes}
        
        # Metrics tracking
        self.metrics = {
            'latencies': [],
            'lost_messages': 0,
            'total_messages': 0,
            'cycle_count': 0
        }
        
        # MQTT client
        self.client = mqtt.Client(client_id=f"Controller_{self.system['intersection_id']}")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
        # CSV logging
        self.setup_csv_logging()
    
    def setup_csv_logging(self):
        """Open CSV file for logging metrics"""
        csv_path = self.config['measurement']['csv_file']
        self.csv_file = open(csv_path, 'w', newline='')
        self.csv_writer = csv.writer(self.csv_file)
        
        # Write header
        self.csv_writer.writerow([
            'timestamp', 'cycle', 'lane', 'avg_density', 'green_time', 
            'latency_ms', 'messages_lost'
        ])
        print(f"✓ Logging to: {csv_path}")
    
    def on_connect(self, client, userdata, flags, rc):
        """Called when connected to MQTT broker"""
        print(f"✓ Controller connected (rc={rc})")
        
        # Subscribe to all sensor topics
        for lane in self.lanes:
            topic = f"traffic/{self.system['intersection_id']}/{lane}/density"
            client.subscribe(topic, qos=self.system['qos_level'])
            print(f"  → Subscribed: {topic}")
    
    def on_message(self, client, userdata, msg):
        """
        Called whenever a sensor message arrives.
        Measures latency and detects lost messages.
        """
        try:
            data = json.loads(msg.payload.decode())
            lane = data['lane']
            
            # ===== LATENCY MEASUREMENT =====
            t_receive = time.time()
            t_publish = data['ts']
            latency_ms = (t_receive - t_publish) * 1000
            
            # ===== MESSAGE LOSS DETECTION =====
            current_seq = data['seq']
            
            with self.lock:  # Thread-safe access
                expected_seq = self.last_seq[lane] + 1
                
                if self.last_seq[lane] >= 0 and current_seq != expected_seq:
                    lost = current_seq - expected_seq
                    self.metrics['lost_messages'] += lost
                    print(f"⚠ Lost {lost} messages on {lane} (seq: {expected_seq} → {current_seq})")
                
                self.last_seq[lane] = current_seq
                self.metrics['total_messages'] += 1
                self.metrics['latencies'].append(latency_ms)
                
                # Store sensor data (with time window limit)
                self.sensor_data[lane].append({
                    'density': data['density_pct'],
                    'queue': data.get('queue_len', 0),
                    'timestamp': t_publish
                })
                
                # Keep only last 30 seconds of data (moving window)
                window = self.config['algorithm']['moving_average_window']
                cutoff = t_receive - window
                self.sensor_data[lane] = [
                    d for d in self.sensor_data[lane] 
                    if d['timestamp'] > cutoff
                ]
            
            # Print received data
            print(f"  [{lane:5}] D={data['density_pct']:5.1f}% | "
                  f"Q={data.get('queue_len', 0):2} | Lat={latency_ms:6.2f}ms")
            
        except Exception as e:
            print(f"✗ Error processing message: {e}")
    
    def compute_green_times(self):
        """
        CORE ALGORITHM: Proportional Allocation
        
        Formula: Green_lane = (Density_lane / Total_Density) × Available_Time
        Constraints: min_green ≤ Green ≤ max_green
        """
        with self.lock:
            # Calculate average density for each lane (last 30 seconds)
            avg_densities = {}
            for lane in self.lanes:
                if self.sensor_data[lane]:
                    densities = [d['density'] for d in self.sensor_data[lane]]
                    avg_densities[lane] = sum(densities) / len(densities)
                else:
                    avg_densities[lane] = 0.0
        
        total_density = sum(avg_densities.values())
        
        # ===== GUARD AGAINST ZERO DENSITY =====
        if total_density <= 0:
            print("⚠ Zero traffic detected - using equal distribution")
            equal = self.timing['cycle_length'] // (len(self.lanes) * 2)
            return {lane: equal for lane in self.lanes}, avg_densities
        
        # Calculate available time for green lights
        cycle = self.timing['cycle_length']
        yellow = self.timing['yellow_time']
        all_red = self.timing['all_red_time']
        n_phases = len(self.lanes)
        
        # Available = Total - (each phase has yellow + all_red)
        available = cycle - n_phases * (yellow + all_red)
        
        # ===== PROPORTIONAL ALLOCATION =====
        raw_greens = {}
        for lane in self.lanes:
            proportion = avg_densities[lane] / total_density
            raw_green = proportion * available
            
            # Apply min/max constraints
            raw_greens[lane] = max(
                self.timing['min_green'],
                min(self.timing['max_green'], raw_green)
            )
        
        # ===== ROUNDING & REDISTRIBUTION =====
        # Convert to integers
        green_times = {lane: int(g) for lane, g in raw_greens.items()}
        
        # Check if sum matches available time
        current_sum = sum(green_times.values())
        diff = available - current_sum
        
        # Distribute leftover seconds to lanes with highest density
        if diff != 0:
            sorted_lanes = sorted(avg_densities.items(), 
                                 key=lambda x: x[1], reverse=True)
            
            for lane, _ in sorted_lanes:
                if diff == 0:
                    break
                adjustment = 1 if diff > 0 else -1
                green_times[lane] += adjustment
                diff -= adjustment
        
        return green_times, avg_densities
    
    def publish_schedule(self, green_times):
        """Send signal timing commands via MQTT"""
        phase_schedule = [
            {
                'lane': lane,
                'green': green_times[lane],
                'yellow': self.timing['yellow_time']
            }
            for lane in self.lanes
        ]
        
        message = {
            'intersection_id': self.system['intersection_id'],
            'cycle_start_ts': time.time(),
            'cycle_length': self.timing['cycle_length'],
            'cycle_count': self.metrics['cycle_count'],
            'phase_schedule': phase_schedule,
            'algorithm': self.config['algorithm']['type']
        }
        
        topic = f"traffic/{self.system['intersection_id']}/commands"
        self.client.publish(topic, json.dumps(message), qos=1)
        
        # Print schedule
        print(f"\n{'='*70}")
        print(f"🚦 CYCLE #{self.metrics['cycle_count']} | {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'='*70}")
        print(f"Algorithm: {self.config['algorithm']['type']}")
        
        total_green = sum(green_times.values())
        print(f"\nGreen Time Schedule (Total: {total_green}s):")
        for lane in self.lanes:
            print(f"  {lane:6} → {green_times[lane]:2}s GREEN + {self.timing['yellow_time']}s YELLOW")
        print(f"{'='*70}\n")
    
    def log_to_csv(self, cycle, green_times, avg_densities):
        """Write cycle data to CSV"""
        avg_latency = (sum(self.metrics['latencies']) / 
                      max(1, len(self.metrics['latencies'])))
        
        for lane in self.lanes:
            self.csv_writer.writerow([
                time.time(),
                cycle,
                lane,
                round(avg_densities.get(lane, 0), 2),
                green_times.get(lane, 0),
                round(avg_latency, 2),
                self.metrics['lost_messages']
            ])
        
        self.csv_file.flush()
    
    def control_loop(self):
        """
        Main control loop - runs every control_interval seconds
        """
        print(f"\n{'='*70}")
        print("🚦 ADAPTIVE TRAFFIC CONTROLLER STARTED")
        print(f"{'='*70}")
        print(f"Algorithm: {self.config['algorithm']['type']}")
        print(f"Control Interval: {self.timing['control_interval']}s")
        print(f"Cycle Length: {self.timing['cycle_length']}s")
        print(f"Green Time Range: {self.timing['min_green']}-{self.timing['max_green']}s")
        print(f"{'='*70}\n")
        
        # Wait a bit for sensors to start publishing
        print("⏳ Waiting 5 seconds for sensor data...")
        time.sleep(5)
        
        try:
            while True:
                # Wait for one control cycle
                time.sleep(self.timing['control_interval'])
                
                # Compute new green times
                green_times, avg_densities = self.compute_green_times()
                
                # Publish schedule
                self.publish_schedule(green_times)
                
                # Log metrics
                self.log_to_csv(self.metrics['cycle_count'], 
                               green_times, avg_densities)
                
                self.metrics['cycle_count'] += 1
                
        except KeyboardInterrupt:
            print("\n\n✗ Controller stopped by user")
        finally:
            self.csv_file.close()
            self.client.disconnect()
            
            # Print final statistics
            print(f"\n{'='*70}")
            print("FINAL STATISTICS")
            print(f"{'='*70}")
            print(f"Total Cycles: {self.metrics['cycle_count']}")
            print(f"Messages Received: {self.metrics['total_messages']}")
            print(f"Messages Lost: {self.metrics['lost_messages']}")
            if self.metrics['latencies']:
                print(f"Average Latency: {sum(self.metrics['latencies'])/len(self.metrics['latencies']):.2f} ms")
            print(f"{'='*70}")
    
    def run(self):
        """Start the controller"""
        self.client.connect(
            self.system['mqtt_broker'],
            self.system['mqtt_port'],
            60
        )
        self.client.loop_start()
        
        # Give time for subscriptions
        time.sleep(1)
        
        # Start control loop
        self.control_loop()


if __name__ == "__main__":
    controller = ProportionalController()
    controller.run()
