#!/usr/bin/env python3
"""
Simple visualization of controller performance
"""

import pandas as pd
import matplotlib.pyplot as plt

# Read CSV data
df = pd.read_csv('results/metrics.csv')

# Create figure with 2 subplots
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

# Plot 1: Density over time
for lane in ['north', 'south', 'east', 'west']:
    lane_data = df[df['lane'] == lane]
    ax1.plot(lane_data['cycle'], lane_data['avg_density'], 
            marker='o', label=lane.capitalize(), linewidth=2)

ax1.set_xlabel('Cycle Number', fontsize=12)
ax1.set_ylabel('Average Density (%)', fontsize=12)
ax1.set_title('Traffic Density Over Time', fontsize=14, fontweight='bold')
ax1.legend()
ax1.grid(True, alpha=0.3)

# Plot 2: Green time allocation
for lane in ['north', 'south', 'east', 'west']:
    lane_data = df[df['lane'] == lane]
    ax2.plot(lane_data['cycle'], lane_data['green_time'], 
            marker='s', label=lane.capitalize(), linewidth=2)

ax2.set_xlabel('Cycle Number', fontsize=12)
ax2.set_ylabel('Green Time (seconds)', fontsize=12)
ax2.set_title('Adaptive Green Time Allocation', fontsize=14, fontweight='bold')
ax2.legend()
ax2.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig('results/performance.png', dpi=150)
print("✓ Graph saved to: results/performance.png")
plt.show()
