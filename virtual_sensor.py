#!/usr/bin/env python3
"""
Virtual Traffic Sensor - Simulates IR sensors detecting vehicles
"""

import paho.mqtt.client as mqtt
import yaml
import json
import time
import random
import math
from datetime import datetime

class VirtualSensor:
    def __init__(self, lane, config_file='config/sensor.yml'):
        # Load configuration
        with open(config_file, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.lane = lane
        self.sequence = 0  # Message counter
        
        # MQTT setup
        self.client = mqtt.Client(client_id=f"Sensor_{lane}")
        
    def connect(self):
        """Connect to MQTT broker"""
        broker = self.config['mqtt']['broker']
        port = self.config['mqtt']['port']
        
        try:
            self.client.connect(broker, port, 60)
            print(f"✓ Sensor [{self.lane}] connected to {broker}:{port}")
            return True
        except Exception as e:
            print(f"✗ Connection failed: {e}")
            return False
    
    def is_peak_hour(self):
        """Check if current time is peak hour"""
        hour = datetime.now().hour
        for start, end in self.config['simulation']['peak_hours']:
            if start <= hour < end:
                return True
        return False
    
    def generate_realistic_density(self):
        """
        Generate realistic traffic density based on time of day.
        Returns: density percentage (0-100)
        """
        # Choose base range based on peak/off-peak
        if self.is_peak_hour():
            base_min, base_max = self.config['simulation']['peak_density_range']
        else:
            base_min, base_max = self.config['simulation']['off_peak_density_range']
        
        # Random value within range
        base_density = random.uniform(base_min, base_max)
        
        # Add smooth noise for realism
        noise = random.gauss(0, self.config['simulation']['noise_stddev'])
        density = base_density + noise
        
        # Clamp to 0-100 range
        return max(0, min(100, density))
    
    def estimate_queue_length(self, density):
        """Estimate queue length from density"""
        # Simple model: higher density = more vehicles waiting
        max_queue = 20
        return int((density / 100) * max_queue)
    
    def publish_density(self):
        """Generate and publish sensor reading"""
        density = self.generate_realistic_density()
        queue = self.estimate_queue_length(density)
        
        # Build message
        message = {
            'intersection_id': 'intersection_1',
            'lane': self.lane,
            'density_pct': round(density, 1),
            'queue_len': queue,
            'seq': self.sequence,
            'ts': time.time()
        }
        
        # Publish to MQTT
        topic = f"traffic/intersection_1/{self.lane}/density"
        payload = json.dumps(message)
        
        result = self.client.publish(
            topic, 
            payload, 
            qos=self.config['mqtt']['qos']
        )
        
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"[{self.lane:5}] Density: {density:5.1f}% | Queue: {queue:2} | Seq: {self.sequence}")
        
        self.sequence += 1
        return density
    
    def run(self, duration=300):
        """Run sensor for specified duration"""
        if not self.connect():
            return
        
        self.client.loop_start()
        
        interval = self.config['simulation']['publish_interval']
        cycles = duration // interval
        
        print(f"\n{'='*60}")
        print(f"Virtual Sensor [{self.lane}] Started")
        print(f"Publishing every {interval}s for {duration}s")
        print(f"{'='*60}\n")
        
        try:
            for i in range(cycles):
                self.publish_density()
                time.sleep(interval)
        except KeyboardInterrupt:
            print(f"\n✗ Sensor [{self.lane}] stopped by user")
        finally:
            self.client.loop_stop()
            self.client.disconnect()
            print(f"✓ Sensor [{self.lane}] disconnected")


def run_all_sensors():
    """Run sensors for all four lanes simultaneously"""
    import threading
    
    lanes = ['north', 'south', 'east', 'west']
    threads = []
    
    print("\n" + "="*70)
    print("STARTING ALL VIRTUAL SENSORS")
    print("="*70)
    
    for lane in lanes:
        sensor = VirtualSensor(lane)
        thread = threading.Thread(target=sensor.run, args=(300,))
        thread.start()
        threads.append(thread)
        time.sleep(0.5)  # Stagger starts slightly
    
    # Wait for all to finish
    for thread in threads:
        thread.join()
    
    print("\n" + "="*70)
    print("ALL SENSORS COMPLETED")
    print("="*70)


if __name__ == "__main__":
    run_all_sensors()
