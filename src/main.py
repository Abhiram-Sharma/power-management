"""
FastAPI application for cyber-physical power management with WebSocket telemetry.
"""

import asyncio
import json
import time
from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


# Import local modules
from sensors import SensorPool
from snn_engine import SNNEngine
from pruner import Pruner


# ============================
# Data Models
# ============================

class TelemetryPacket(BaseModel):
    """WebSocket telemetry message payload."""
    timestamp: float
    temperature: float
    voltage: float
    active_synapses: int
    is_pruning: bool


class SensorMetrics(BaseModel):
    """REST API sensor data response."""
    timestamp: float
    temperature: float
    voltage: float
    platform: str
    sensor_id: str


class StatusResponse(BaseModel):
    """System status response."""
    status: str
    sensors_online: int
    active_synapses: int
    is_pruning: bool
    timestamp: float


# ============================
# Application State
# ============================

class ApplicationState:
    """Global application state for managing components."""
    def __init__(self):
        self.sensor_pool: SensorPool = SensorPool(polling_interval_ms=10)
        self.snn_engine: SNNEngine = SNNEngine(
            input_size=128,
            hidden_sizes=[256, 128, 64],
            output_size=32,
            sparsity=0.85,
        )
        self.pruner: Pruner = Pruner(
            temperature_threshold=45.0,
            pruning_percentage=0.20,
            polling_interval_ms=10, # Changed from 100 to match telemetry
        )
        self.pruner.bind_snn_engine(self.snn_engine)
        self.pruner.bind_sensor_pool(self.sensor_pool) # Inject the shared pool

        # WebSocket connections
        self.active_connections: List[WebSocket] = []

        # Background tasks
        self._telemetry_task = None
        self._polling_task = None
        self._running = False

    async def start(self):
        """Start all background tasks."""
        self._running = True

        # Start SNN engine
        self.snn_engine.start()

        # Start pruner monitoring
        self.pruner.start()

        # Start telemetry broadcast loop
        self._telemetry_task = asyncio.create_task(self._telemetry_loop())

        # Start sensor polling loop
        self._polling_task = asyncio.create_task(self._sensor_polling_loop())

    async def stop(self):
        """Stop all background tasks and clean up."""
        self._running = False

        # Stop telemetry broadcast
        if self._telemetry_task:
            self._telemetry_task.cancel()
            try:
                await self._telemetry_task
            except asyncio.CancelledError:
                pass

        # Stop sensor polling
        if self._polling_task:
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass

        # Stop pruner
        self.pruner.stop()

        # Stop SNN engine
        self.snn_engine.stop()

        # Close all WebSocket connections
        for connection in self.active_connections:
            try:
                await connection.close()
            except Exception:
                pass
        self.active_connections.clear()

    async def _telemetry_loop(self):
        """Broadcast telemetry to all WebSocket clients every 10ms."""
        while self._running:
            try:
                # Get current metrics
                metrics = self.sensor_pool.get_current_values()

                telemetry = TelemetryPacket(
                    timestamp=time.time(),
                    temperature=metrics.get("temperature", 0.0),
                    voltage=metrics.get("voltage", 0.0),
                    active_synapses=self.snn_engine.get_active_synapses(),
                    is_pruning=is_pruning(self.pruner),
                )

                # Broadcast to all clients
                message = json.dumps(telemetry.dict())
                for connection in self.active_connections:
                    try:
                        await connection.send_text(message)
                    except Exception:
                        # Remove disconnected clients
                        self.active_connections.remove(connection)

                # Sleep for 10ms (100Hz)
                await asyncio.sleep(0.01)
            except asyncio.CancelledError:
                break
            except Exception:
                # Log error but continue broadcasting
                pass

    async def _sensor_polling_loop(self):
        """Poll sensors at 10ms intervals."""
        while self._running:
            try:
                await self.sensor_pool.poll_sensors()
                await asyncio.sleep(0.01)
            except asyncio.CancelledError:
                break
            except Exception:
                pass


def is_pruning(pruner: Pruner) -> bool:
    """Helper to check if pruning is in progress."""
    stats = pruner.get_stats()
    return stats.get("pruning_in_progress", False)


# ============================
# Application Factory
# ============================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown."""
    # Startup
    app.state.app_state = ApplicationState()
    await app.state.app_state.start()
    yield
    # Shutdown
    await app.state.app_state.stop()


app = FastAPI(
    title="Cyber-Physical Power Management System",
    description="Real-time SNN engine with hardware-state triggered pruning",
    lifespan=lifespan,
)

# Configure CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================
# REST API Endpoints
# ============================

@app.get("/status", response_model=StatusResponse)
async def get_status():
    """Get system health status."""
    state = app.state.app_state

    metrics = state.sensor_pool.get_current_values()

    return StatusResponse(
        status="degraded" if state.pruner.get_stats()["pruning_in_progress"] else "healthy",
        sensors_online=1,
        active_synapses=state.snn_engine.get_active_synapses(),
        is_pruning=is_pruning(state.pruner),
        timestamp=time.time(),
    )


@app.get("/sensor/history", response_model=List[SensorMetrics])
async def get_sensor_history(limit: int = 100):
    """Get recent sensor data history."""
    state = app.state.app_state
    data = state.sensor_pool.get_recent_data(limit)

    return [
        SensorMetrics(
            timestamp=m.get("timestamp", 0),
            temperature=m.get("temperature", 0),
            voltage=m.get("voltage", 0),
            platform=m.get("platform", "unknown"),
            sensor_id=m.get("sensor_id", "unknown"),
        )
        for m in data
    ]


@app.get("/pruning/history")
async def get_pruning_history(limit: int = 100):
    """Get pruning event history."""
    state = app.state.app_state
    stats = state.pruner.get_stats()

    return {
        "pruning_count": stats.get("pruning_count", 0),
        "last_pruning_temp": stats.get("last_pruning_temp", 0),
        "threshold": stats.get("threshold", 0),
        "timestamp": time.time(),
    }


# ============================
# WebSocket Endpoint
# ============================

@app.websocket("/ws/telemetry")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time telemetry streaming.

    Broadcasts JSON packets at 10Hz containing:
    - timestamp, temperature, voltage, active_synapses, is_pruning
    """
    await websocket.accept()
    state = app.state.app_state

    # Register connection
    state.active_connections.append(websocket)

    try:
        while True:
            # Wait for messages (for client disconnection detection)
            data = await websocket.receive_text()

            # Handle client messages (ping/pong, commands)
            if data == "ping":
                await websocket.send_text("pong")
            elif data == "subscribe":
                # Client subscribes to telemetry stream
                await websocket.send_text(json.dumps({
                    "type": "subscribed",
                    "timestamp": time.time(),
                }))
    except WebSocketDisconnect:
        # Client disconnected
        state.active_connections.remove(websocket)
    except Exception:
        # Other errors - remove client
        if websocket in state.active_connections:
            state.active_connections.remove(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)