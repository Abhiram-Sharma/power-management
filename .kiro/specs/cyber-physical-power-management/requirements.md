# Cyber-Physical Power Management System - Requirements

## Overview
Real-time edge computing system for spiking neural networks with hardware-state triggered synaptic pruning and WebSocket-based telemetry.

## Functional Requirements

### 1. Hardware Polling (10ms Interval)
- **FR-1.1**: Poll hardware sensors at exactly 10ms intervals
- **FR-1.2**: Support dual-platform sensor reading:
  - Windows: Mock sensors via psutil (CPU temp, memory usage)
  - Linux/Raspberry Pi: Raw thermal files from `/sys/class/thermal/`
- **FR-1.3**: Buffer sensor readings in circular buffer (100 samples minimum)
- **FR-1.4**: Report sensor ReadFailure events with retry logic (max 3 attempts)

### 2. Physical-State Triggered Synaptic Pruning
- **FR-2.1**: Monitor thermal and power metrics for pruning triggers:
  - Temperature > 75°C: Activate aggressive pruning
  - Temperature > 65°C: Activate moderate pruning
  - Power draw > threshold: Activate emergency pruning
- **FR-2.2**: Apply pruning via PyTorch sparse tensor operations
- **FR-2.3**: Log pruning events with timestamp and trigger conditions
- **FR-2.4**: Maintain pruning history (last 100 events) in memory

### 3. Real-Time Telemetry via WebSockets
- **FR-3.1**: WebSocket endpoint `/ws/telemetry` for real-time streaming
- **FR-3.2**: Broadcast sensor readings at 10Hz (100ms intervals)
- **FR-3.3**: Broadcast pruning events immediately on occurrence
- **FR-3.4**: Support multiple concurrent WebSocket connections
- **FR-3.5**: Send JSON-serialized telemetry messages:
  - `sensor_data`: {timestamp, cpu_temp, memory_pct, power_draw, sensor_id}
  - `pruning_event`: {timestamp, trigger, neurons_pruned, sparsity_ratio}
- **FR-3.6**: Graceful WebSocket disconnection handling (retry connection on client)

### 4. REST API Endpoints
- **FR-4.1**: `GET /status` - System health status
- **FR-4.2**: `GET /sensor/history?limit=100` - Recent sensor data
- **FR-4.3**: `GET /pruning/history?limit=100` - Pruning event log
- **FR-4.4**: `POST /pruning/config` - Update pruning thresholds

### 5. Error Handling
- **FR-5.1**: Catch file read errors for Linux thermal sensors
- **FR-5.2**: Handle psutil exceptions on Windows gracefully
- **FR-5.3**: Log all errors to system log file
- **FR-5.4**: Implement circuit breaker for repeated sensor failures

## Non-Functional Requirements
- **NFR-1**: Startup time < 5 seconds on Raspberry Pi 5
- **NFR-2**: Memory footprint < 500MB under normal load
- **NFR-3**: WebSocket latency < 50ms for telemetry updates
- **NFR-4**: Support 10+ concurrent WebSocket connections