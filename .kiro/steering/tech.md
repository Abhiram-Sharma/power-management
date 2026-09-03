# Technical Requirements

## Target Runtime
- Python 3.11.2 (strictly enforced)
- Use virtual environments to ensure version isolation

## Development Platform
- Windows (development/testing)
- Hardware sensors must be mocked for local development
- Use `psutil` for system metrics (CPU, memory, temperature) as available

## Deployment Platform
- Raspberry Pi 5 / Linux (production)
- Reads raw thermal files from `/sys/class/thermal/`
- Uses standard ARM/Linux interfaces without custom hardware assumptions

## System Architecture

### Core Principles
- Asynchronous execution loop for non-blocking operations
- Decoupled sensor polling with configurable intervals
- WebSocket-based telemetry for real-time monitoring

### Components
- FastAPI for REST API endpoints
- Uvicorn ASGI server for async request handling
- PyTorch for spiking neural network processing
- WebSockets for live telemetry streaming
- psutil for cross-platform system metrics

### Sensor Interface
- Abstract sensor layer supporting both mocked (Windows) and raw Linux interfaces
- Thermal sensor reads from `/sys/class/thermal/thermal_zone*/temp` on Linux
- Mock sensors for development on Windows using simulated values

### Telemetry
- Real-time WebSocket updates for sensor data
- Decoupled polling mechanism to avoid blocking
- Graceful degradation when hardware is unavailable