# MQTT Message Specification

## Sensor → Controller (Traffic Density)

**Topic Pattern:** `traffic/{intersection_id}/{lane}/density`

**Example Topics:**
- traffic/intersection_1/north/density
- traffic/intersection_1/south/density
- traffic/intersection_1/east/density
- traffic/intersection_1/west/density

**Message Format (JSON):**
{
"intersection_id": "intersection_1",
"lane": "north",
"density_pct": 75.0,
"queue_len": 12,
"seq": 1234,
"ts": 1729401234.567
}


**Fields:**
- `density_pct`: Traffic density 0-100%
- `queue_len`: Number of vehicles waiting
- `seq`: Sequence number (for detecting lost messages)
- `ts`: Unix timestamp when message was created

## Controller → Signals (Commands)

**Topic:** `traffic/{intersection_id}/commands`

**Message Format:**
{
"intersection_id": "intersection_1",
"cycle_start_ts": 1729401236.0,
"cycle_length": 60,
"phase_schedule": [
{"lane": "north", "green": 25, "yellow": 3},
{"lane": "south", "green": 15, "yellow": 3},
{"lane": "east", "green": 12, "yellow": 3},
{"lane": "west", "green": 8, "yellow": 3}
]
}

undefined
