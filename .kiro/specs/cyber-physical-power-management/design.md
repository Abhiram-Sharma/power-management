# Cyber-Physical Power Management System - Design

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        FastAPI App                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │   Sensors    │  │   SNN Engine │  │   Pruner       │  │
│  │   Polling    │  │   Processing │  │   Triggered    │  │
│  │   Loop       │  │   & Pruning  │  │   Logic        │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│                       │          │                          │
│              ┌──────────────────┼──────────────────┐       │
│              │                  │                  │       │
│       ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│       │ WebSocket    │  │   REST API   │  │   Logging    │ │
│       │ Telemetry    │  │   Endpoints  │  │   System     │ │
│       └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Component Specification

### 1. sensors.py
**Purpose**: Hardware sensor abstraction layer

**Class**: `SensorPool`
- `async poll_sensors()` - Read all sensors at 10ms intervals
- `get_recent_data(limit=100)` - Return buffered sensor readings
- `get_current_values()` - Return most recent reading
- `reset_buffer()` - Clear circular buffer

**Platform-specific implementations**:
- `WindowsSensorReader` - Uses psutil for CPU temp, memory, power
- `LinuxSensorReader` - Reads `/sys/class/thermal/thermal_zone*/temp`

**Data Contract**:
```json
{
  "timestamp": "2024-01-15T10:30:00.000Z",
  "cpu_temp_c": 45.2,
  "memory_pct": 32.5,
  "power_draw_w": 3.8,
  "sensor_id": "raspi5-001"
}
```

### 2. snn_engine.py
**Purpose**: Spiking neural network processing

**Class**: `SNNEngine`
- `async process_inputs(inputs)` - Process input spikes
- `get_sparsity()` - Return current network sparsity
- `get_active_neurons()` - Count active neurons

**Dependencies**: PyTorch sparse tensors

### 3. pruner.py
**Purpose**: Hardware-state triggered pruning

**Class**: `Pruner`
- `async check_and_prune(sensors)` - Evaluate sensors, trigger pruning if needed
- `configure_thresholds(temp_high, temp_med, power)` - Update pruning thresholds
- `get_pruning_history(limit=100)` - Return pruning events
- `record_pruning(trigger, neurons_pruned, sparsity)` - Log pruning event

**Pruning Triggers**:
- Temperature > 75°C → aggressive (50% neurons)
- Temperature > 65°C → moderate (25% neurons)
- Power > threshold → emergency (75% neurons)

**Data Contract**:
```json
{
  "timestamp": "2024-01-15T10:30:00.000Z",
  "trigger": "temperature_high",
  "neurons_pruned": 512,
  "sparsity_ratio": 0.75
}
```

### 4. main.py
**Purpose**: Application entry point and orchestration

**Class**: `PowerManagementApp`
- `async start()` - Initialize and start all components
- `async stop()` - Graceful shutdown
- `register_websocket_handler(ws)` - Add WebSocket connection
- `broadcast_telemetry(message)` - Send to all WebSocket clients

**Thread Management**:
- Main thread: FastAPI request handling
- Async loop: Sensor polling (10ms), pruning checks (100ms)
- WebSocket broadcast: Non-blocking async

**Error Handling**:
- Try-except around sensor reads with retry logic
- Circuit breaker pattern for repeated failures
- Fallback to mock sensors if hardware unavailable

## Data Contracts

### Telemetry Message (WebSocket)
```json
{
  "type": "sensor_data" | "pruning_event",
  "data": { /* sensor or pruning data */ },
  "timestamp": "2024-01-15T10:30:00.000Z"
}
```

### REST API Responses
- `/status`: `{status: "healthy" | "degraded", sensors_online: int}`
- `/sensor/history`: `[{sensor_data}, ...]`
- `/pruning/history`: `[{pruning_event}, ...]`

## Module Dependencies

```
main.py
 ├── sensors.py
 │   └── (psutil on Windows, sysfs on Linux)
 ├── snn_engine.py
 │   └── torch
 ├── pruner.py
 │   ├── sensors.py
 │   └── snn_engine.py
 └── (WebSocket broadcasting)
```

## Error Handling Strategy

1. **Sensor Read Failures**: Retry 3 times, then fallback to last known value
2. **Thermal File Not Found**: Log warning, use mock sensors
3. **WebSocket Disconnect**: Remove from client list, retry on next broadcast
4. **PyTorch Processing Errors**: Log, continue with current state