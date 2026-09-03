# Cyber-Physical Power Management System - Implementation Tasks

## Phase 1: Core Infrastructure

### Task 1.1: Set up Python environment and install dependencies
- [ ] Create virtual environment with Python 3.11.2
- [ ] Install dependencies from requirements.txt
- [ ] Verify version: `python --version` → 3.11.2
- **Test**: `pip list | grep -E "fastapi|uvicorn|torch|psutil|websockets"`

### Task 1.2: Create project structure
- [ ] Create `src/` directory
- [ ] Create `src/__init__.py` (empty)
- [ ] Create `src/sensors.py`
- [ ] Create `src/snn_engine.py`
- [ ] Create `src/pruner.py`
- [ ] Create `src/main.py`
- [ ] Create `config.json` for thresholds
- **Test**: Run `python -c "import src"` without errors

---

## Phase 2: Sensor Layer (Independent - No Dependencies)

### Task 2.1: Implement sensor base class
- [ ] Create abstract `SensorReader` base class
- [ ] Implement `get_current_values()` method
- [ ] Implement `get_recent_data(limit)` method
- [ ] Implement circular buffer (collections.deque)
- **Test**: `pytest tests/test_sensors.py` → test_sensor_base

### Task 2.2: Implement Windows sensor reader
- [ ] Create `WindowsSensorReader` class
- [ ] Use psutil for CPU temp, memory, power
- [ ] Mock sensor ID as "windows-dev"
- [ ] Handle psutil exceptions gracefully
- **Test**: Run on Windows machine, verify sensor values

### Task 2.3: Implement Linux sensor reader
- [ ] Create `LinuxSensorReader` class
- [ ] Read `/sys/class/thermal/thermal_zone*/temp`
- [ ] Parse milli-celsius to Celsius
- [ ] Use `os.listdir()` to discover thermal zones
- **Test**: Run on Linux/Raspberry Pi, verify thermal files exist

### Task 2.4: Create sensor pool aggregator
- [ ] Create `SensorPool` class
- [ ] Auto-detect platform and instantiate reader
- [ ] Implement `poll_sensors()` async method
- [ ] Implement buffer management (100 samples)
- **Test**: `SensorPool().get_current_values()` returns dict

---

## Phase 3: SNN Engine (Independent - No Dependencies)

### Task 3.1: Create basic SNN engine
- [ ] Create `SNNEngine` class
- [ ] Initialize sparse tensor network (random 1000 neurons)
- [ ] Implement `process_inputs(inputs)` - mock processing
- [ ] Track active neurons count
- **Test**: `SNNEngine().process_inputs([1,0,1])` returns result

### Task 3.2: Add sparsity tracking
- [ ] Implement `get_sparsity()` method
- [ ] Implement `get_active_neurons()` method
- [ ] Update on each processing cycle
- **Test**: Verify sparsity > 0 after pruning

---

## Phase 4: Pruner (Dependencies: sensors, snn_engine)

### Task 4.1: Implement threshold configuration
- [ ] Create `Pruner` class
- [ ] Load thresholds from `config.json`
- [ ] Default: temp_high=75, temp_med=65, power=5.0
- **Test**: Load config, verify defaults

### Task 4.2: Implement pruning logic
- [ ] `check_and_prune(sensors)` - Evaluate conditions
- [ ] Trigger aggressive pruning (50%) if temp > 75
- [ ] Trigger moderate pruning (25%) if temp > 65
- [ ] Trigger emergency pruning (75%) if power > threshold
- **Test**: Simulate high temp, verify pruning triggers

### Task 4.3: Implement pruning history
- [ ] Create circular buffer for 100 events
- [ ] Store: timestamp, trigger type, neurons pruned, sparsity
- [ ] Implement `get_pruning_history(limit)`
- **Test**: Add 105 events, verify buffer size = 100

---

## Phase 5: WebSocket Telemetry (Dependencies: sensors, pruner)

### Task 5.1: Implement WebSocket endpoint
- [ ] Create `/ws/telemetry` endpoint in FastAPI
- [ ] Accept multiple connections
- [ ] Handle disconnections gracefully
- **Test**: Connect via WebSocket client, verify connection

### Task 5.2: Implement sensor data broadcasting
- [ ] Broadcast at 10Hz (100ms intervals)
- [ ] Format: `{"type":"sensor_data", "data": {...}}`
- [ ] Include timestamp, temp, memory, power, sensor_id
- **Test**: WebSocket client receives 10 messages/second

### Task 5.3: Implement pruning event broadcasting
- [ ] Broadcast immediately on pruning trigger
- [ ] Format: `{"type":"pruning_event", "data": {...}}`
- [ ] Include timestamp, trigger, neurons_pruned, sparsity
- **Test**: Pruning triggers event, client receives immediately

---

## Phase 6: REST API Endpoints (Dependencies: sensors, pruner)

### Task 6.1: Implement `/status` endpoint
- [ ] Return system health status
- [ ] Include sensor count online
- [ ] Return "healthy" or "degraded"
- **Test**: `curl http://localhost:8000/status`

### Task 6.2: Implement `/sensor/history` endpoint
- [ ] Accept `limit` query parameter
- [ ] Return buffered sensor data
- [ ] JSON serialization
- **Test**: `curl http://localhost:8000/sensor/history?limit=10`

### Task 6.3: Implement `/pruning/history` endpoint
- [ ] Accept `limit` query parameter
- [ ] Return pruning events
- **Test**: `curl http://localhost:8000/pruning/history`

### Task 6.4: Implement `/pruning/config` endpoint
- [ ] POST to update thresholds
- [ ] Validate input (temp: 0-100, power: positive)
- [ ] Update config.json
- **Test**: POST new thresholds, verify update

---

## Phase 7: Integration and Testing

### Task 7.1: Asynchronous loop orchestration
- [ ] Create `PowerManagementApp` class
- [ ] Start sensor polling loop (10ms)
- [ ] Start pruning check loop (100ms)
- [ ] Handle graceful shutdown on SIGTERM
- **Test**: Start app, verify all loops running

### Task 7.2: Error handling integration
- [ ] Test sensor read failures
- [ ] Test WebSocket client disconnects
- [ ] Test thermal file not found
- **Test**: Simulate failures, verify error logs

### Task 7.3: Platform-specific testing
- [ ] Test on Windows (mock sensors)
- [ ] Test on Linux (real thermal files)
- [ ] Verify identical API responses
- **Test**: Run same test script on both platforms

---

## Phase 8: Optimization and Documentation

### Task 8.1: Performance tuning
- [ ] Profile memory usage (< 500MB target)
- [ ] Optimize WebSocket broadcast latency (< 50ms)
- [ ] Reduce CPU usage on idle
- **Test**: `python -m memory_profiler main.py`

### Task 8.2: Create deployment guide
- [ ] Windows setup instructions
- [ ] Raspberry Pi 5 setup instructions
- [ ] systemd service file for Linux
- [ ] Environment variable documentation

### Task 8.3: Final validation
- [ ] All FR-1 through FR-5 requirements verified
- [ ] All NFR-1 through NFR-4 requirements verified
- [ ] Run full integration test suite
- **Test**: `pytest tests/` → 100% pass