"""
Hardware sensor abstraction layer for cyber-physical power management.
Supports Linux (Raspberry Pi) thermal sensors and Windows mock telemetry.
"""

import asyncio
import os
import platform
import random
import time
from pathlib import Path


class SensorPool:
    """Polls hardware sensors at high frequency (10ms)."""

    def __init__(self, polling_interval_ms: int = 10):
        self.polling_interval_ms = polling_interval_ms
        self.buffer: list[dict] = []
        self.max_buffer_size = 100
        self._platform = platform.system()
        self._last_temp = 40.0  # Initial temperature estimate

        if self._platform == "Linux":
            self._reader = LinuxSensorReader()
        elif self._platform == "Windows":
            self._reader = WindowsSensorReader()
        else:
            raise NotImplementedError(f"Unsupported platform: {self._platform}")

    async def poll_sensors(self) -> dict:
        """Poll sensors and return latest metrics."""
        metrics = self._reader.get_metrics()
        self.buffer.append(metrics)

        # Maintain circular buffer
        if len(self.buffer) > self.max_buffer_size:
            self.buffer.pop(0)

        return metrics

    def get_recent_data(self, limit: int = 100) -> list[dict]:
        """Return buffered sensor readings."""
        return self.buffer[-limit:]

    def get_current_values(self) -> dict:
        """Return most recent reading or default."""
        if self.buffer:
            return self.buffer[-1]
        return {"temperature": 0.0, "voltage": 0.0, "timestamp": time.time()}


class LinuxSensorReader:
    """Reads raw thermal data from Linux /sys/class/thermal interface."""

    def __init__(self):
        self.thermal_zone = Path("/sys/class/thermal/thermal_zone0/temp")

    def get_metrics(self) -> dict:
        """Read SoC substrate temperature from thermal zone."""
        try:
            temp_raw = self.thermal_zone.read_text().strip()
            temperature = float(temp_raw) / 1000.0  # Convert milli-celsius to Celsius
        except (FileNotFoundError, ValueError, PermissionError) as e:
            temperature = self._fallback_temperature()

        return {
            "temperature": temperature,
            "voltage": 5.0,  # Raspberry Pi constant 5V supply
            "timestamp": time.time(),
            "platform": "Linux",
            "sensor_id": "linux-thermal-zone0",
        }

    def _fallback_temperature(self) -> float:
        """Return last known temperature if sensor read fails."""
        return self._last_temp


class WindowsSensorReader:
    """Generates mock telemetry for Windows development/testing."""

    def __init__(self):
        self._start_time = time.time()
        self._base_voltage = 4.1
        self._voltage_drift_rate = -0.0001  
        self._cooling_decrement = 0.0  
        self._current_temp = 40.0 # Track physical state over time

    def get_metrics(self) -> dict:
        elapsed = time.time() - self._start_time

        # Smooth Random Walk: Heat climbs steadily under load with minor fluctuations
        self._current_temp += random.uniform(-0.02, 0.08)
        
        temperature = self._current_temp - self._cooling_decrement
        temperature = max(38.0, min(48.0, temperature))

        voltage = self._base_voltage + (self._voltage_drift_rate * elapsed)
        voltage = max(3.7, min(4.2, voltage)) 

        return {
            "temperature": round(temperature, 2),
            "voltage": round(voltage, 3),
            "timestamp": time.time(),
            "platform": "Windows",
            "sensor_id": "windows-mock",
        }

    def apply_cooling(self, degrees: float = 3.0) -> None:
        """Simulate silicon cooling after pruning (Windows mock only)."""
        self._cooling_decrement += degrees


def get_hardware_metrics() -> dict:
    """
    Unified function to get current hardware metrics.

    Returns:
        dict with keys: temperature, voltage, timestamp, platform, sensor_id
    """
    pool = SensorPool(polling_interval_ms=10)
    # Initialize buffer with one sample
    asyncio.run(pool.poll_sensors())
    return pool.get_current_values()


async def main():
    """Main entry point for direct execution - polls and prints every 10ms."""
    pool = SensorPool(polling_interval_ms=10)

    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting sensor polling on {platform.system()}")
    print(f"Interval: {pool.polling_interval_ms}ms | Buffer size: {pool.max_buffer_size}")

    try:
        while True:
            metrics = await pool.poll_sensors()
            print(
                f"[{time.strftime('%H:%M:%S')}] "
                f"Temp: {metrics['temperature']:>6.2f}°C | "
                f"Volt: {metrics['voltage']:>5.2f}V | "
                f"Platform: {metrics['platform']}"
            )
            await asyncio.sleep(pool.polling_interval_ms / 1000.0)
    except KeyboardInterrupt:
        print("\n[INFO] Stopping sensor polling...")
    finally:
        print(f"[INFO] Collected {len(pool.buffer)} sensor samples")


if __name__ == "__main__":
    asyncio.run(main())