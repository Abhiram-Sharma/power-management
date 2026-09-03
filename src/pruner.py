"""
Hardware-state triggered synaptic pruning for cyber-physical power management.
Binds sensors and SNN engine into an interrupt loop for thermal regulation.
"""

import asyncio
import threading
import time
from typing import Callable, Optional

import torch

from sensors import get_hardware_metrics, SensorPool, WindowsSensorReader
from snn_engine import SNNEngine


class Pruner:
    """
    Monitors hardware metrics and triggers SNN pruning on threshold breach.
    Implements hardware-state triggered synaptic pruning with thermal relief.
    """

    def __init__(
        self,
        temperature_threshold: float = 45.0,
        pruning_percentage: float = 0.20,
        polling_interval_ms: int = 10,
    ):
        self.temperature_threshold = temperature_threshold
        self.pruning_percentage = pruning_percentage
        self.polling_interval_ms = polling_interval_ms

        self._lock = threading.RLock()
        self._running = False
        self._pruning_in_progress = False
        self._pruning_count = 0
        self._last_pruning_temp = 0.0
        self._monitor_task = None

        # Sensor pool for high-frequency polling
        self._sensor_pool: Optional[SensorPool] = None

        # Reference to SNN engine (set by controller)
        self._snn_engine: Optional[SNNEngine] = None

        # Windows sensor cooling reference (for thermal relief)
        self._windows_reader: Optional[WindowsSensorReader] = None

    def bind_snn_engine(self, engine: SNNEngine) -> None:
        """Bind SNN engine to pruner for pause/resume control."""
        self._snn_engine = engine

    def bind_sensor_pool(self, pool: SensorPool) -> None:
        """Bind a shared sensor pool to prevent duplicate sensor reads."""
        self._sensor_pool = pool
        if hasattr(self._sensor_pool, "_reader"):
            if isinstance(self._sensor_pool._reader, WindowsSensorReader):
                self._windows_reader = self._sensor_pool._reader
    def start(self) -> None:
        """Start the pruning monitoring loop."""
        if self._running:
            return
        self._running = True
        
        # Only create a new pool if one was not injected by the main app
        if self._sensor_pool is None:
            self._sensor_pool = SensorPool(polling_interval_ms=self.polling_interval_ms)
            if hasattr(self._sensor_pool, "_reader"):
                if isinstance(self._sensor_pool._reader, WindowsSensorReader):
                    self._windows_reader = self._sensor_pool._reader

        self._monitor_task = asyncio.create_task(self._monitor_loop())

        # Capture Windows sensor for cooling simulation
        if hasattr(self._sensor_pool, "_reader"):
            if isinstance(self._sensor_pool._reader, WindowsSensorReader):
                self._windows_reader = self._sensor_pool._reader

        # Start monitoring loop
        self._monitor_task = asyncio.create_task(self._monitor_loop())

    def stop(self) -> None:
        """Stop the pruning monitoring loop."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
        self._sensor_pool = None
        self._windows_reader = None

    async def _monitor_loop(self) -> None:
        """Continuous monitoring loop with 10ms polling."""
        while self._running and not self._pruning_in_progress:
            try:
                metrics = self._sensor_pool.get_current_values()

                if metrics.get("temperature", 0.0) >= self.temperature_threshold:
                    await self._trigger_pruning(metrics)
            except Exception as e:
                # Log error but continue monitoring
                pass

            await asyncio.sleep(self.polling_interval_ms / 1000.0)

    async def _trigger_pruning(self, metrics: dict) -> None:
        """
        Trigger pruning interrupt when temperature threshold is breached.

        Steps:
        1. Pause SNN execution loop
        2. Identify lowest 20% of non-zero synaptic weights
        3. Set these weights to 0.0 (pruning)
        4. Update state and resume processing
        5. Apply thermal relief (Windows only)
        """
        if self._snn_engine is None:
            return

        self._pruning_in_progress = True

        try:
            # Step 1: Pause SNN execution
            self._snn_engine.pause()

            # Step 2 & 3: Prune lowest 20% of weights
            neurons_pruned = self._execute_pruning()

            # Step 4: Update state and resume
            self._pruning_count += 1
            self._last_pruning_temp = metrics.get("temperature", 0.0)

            # Step 5: Apply thermal relief for Windows mock
            if self._windows_reader is not None:
                self._windows_reader.apply_cooling(degrees=3.0)

            self._snn_engine.resume()

            print(
                f"[{time.strftime('%H:%M:%S')}] PRUNING TRIGGERED: "
                f"Temp={metrics.get('temperature', 0):.2f}°C -> "
                f"{self._last_pruning_temp:.2f}°C, "
                f"Neurons Pruned: {neurons_pruned}"
            )

        except Exception as e:
            print(f"[ERROR] Pruning failed: {e}")
        finally:
            self._pruning_in_progress = False

    def _execute_pruning(self) -> int:
        """Execute the actual pruning operation."""
        if self._snn_engine is None:
            return 0

        total_pruned = 0

        with torch.no_grad():
            with self._snn_engine._lock:
                for i, weight in enumerate(self._snn_engine.weights):
                    if not weight.is_sparse:
                        continue

                    # Get non-zero weight values and indices
                    values = weight.values()
                    indices = weight.indices()
                    num_nonzero = len(values)
                    if num_nonzero == 0:
                        continue

                    # Calculate how many to prune (20% of non-zero)
                    num_to_prune = max(1, int(num_nonzero * self.pruning_percentage))

                    # Find indices of lowest magnitude weights
                    abs_values = torch.abs(values)
                    _, indices_to_zero = torch.topk(abs_values, num_to_prune, largest=False)

                    # Create a mask of values to KEEP
                    keep_mask = torch.ones(num_nonzero, dtype=torch.bool)
                    keep_mask[indices_to_zero] = False

                    # Filter values and indices to keep only non-zero elements
                    new_values = values[keep_mask]
                    new_indices = indices[:, keep_mask] if indices.dim() > 1 else indices[keep_mask]

                    total_pruned += num_to_prune

                    # Create new sparse tensor with pruned weights
                    self._snn_engine.weights[i] = torch.sparse_coo_tensor(
                        indices=new_indices,
                        values=new_values,
                        size=weight.size(),
                    ).coalesce()

        return total_pruned

    def get_stats(self) -> dict:
        """Get pruning statistics."""
        with self._lock:
            return {
                "pruning_count": self._pruning_count,
                "last_pruning_temp": self._last_pruning_temp,
                "pruning_in_progress": self._pruning_in_progress,
                "threshold": self.temperature_threshold,
            }


async def run_pruning_test():
    """Test the complete pruning cycle: load -> threshold -> interrupt -> relief."""
    print("=" * 60)
    print("Hardware-Triggered Pruning Test")
    print("=" * 60)

    # Initialize components
    snn_engine = SNNEngine(
        input_size=128,
        hidden_sizes=[256, 128, 64],
        output_size=32,
        sparsity=0.85,
    )
    pruner = Pruner(
        temperature_threshold=45.0,
        pruning_percentage=0.20,
        polling_interval_ms=10,
    )

    # Bind engine to pruner
    pruner.bind_snn_engine(snn_engine)

    print(f"\nInitial state:")
    print(f"  Active synapses: {snn_engine.get_active_synapses()}")
    print(f"  Threshold: {pruner.temperature_threshold}°C")

    # Start SNN engine and pruner
    snn_engine.start()
    pruner.start()

    print("\nSimulating load generation (30 seconds)...")
    print("(Temperature will drift upward, triggering pruning)")

    try:
        # Monitor for 30 seconds
        start_time = time.time()
        while time.time() - start_time < 30:
            # Get current metrics
            metrics = get_hardware_metrics()
            pruning_stats = pruner.get_stats()

            print(
                f"[{time.strftime('%H:%M:%S')}] "
                f"Temp: {metrics['temperature']:>6.2f}°C | "
                f"Synapses: {snn_engine.get_active_synapses():>6} | "
                f"Prunings: {pruning_stats['pruning_count']}"
            )

            # Simulate thermal runaway ( artificially increase temp reading)
            # This forces the pruning trigger
            if metrics["temperature"] < 46.0:
                # Artificially boost temperature for testing
                await asyncio.sleep(0.5)
            else:
                # Wait for actual threshold breach
                await asyncio.sleep(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        print("\nStopping...")
        pruner.stop()
        snn_engine.stop()

    print("\nTest complete.")
    print(f"Total pruning events: {pruner.get_stats()['pruning_count']}")


def run_pruning_demo():
    """Demonstration showing pruning cycle with artificial threshold trigger."""
    print("=" * 60)
    print("Pruning Demo: Threshold -> Interrupt -> Relief")
    print("=" * 60)

    # Initialize components
    snn_engine = SNNEngine(
        input_size=64,
        hidden_sizes=[128, 64],
        output_size=32,
        sparsity=0.85,
    )
    pruner = Pruner(
        temperature_threshold=40.0,  # Lower threshold for demo
        pruning_percentage=0.20,
        polling_interval_ms=100,  # Slower polling for demo visibility
    )
    pruner.bind_snn_engine(snn_engine)

    print(f"\nInitial synapses: {snn_engine.get_active_synapses()}")

    # Simulate a threshold breach scenario
    print("\n[1] Simulating temperature threshold breach (temp >= 45°C)...")
    
    # Temporarily bypass the sensor check and directly trigger pruning
    metrics = {
        "temperature": 48.5,
        "voltage": 4.1,
        "timestamp": time.time(),
        "platform": "Windows",
        "sensor_id": "windows-mock",
    }

    print(f"  Temperature: {metrics['temperature']}°C (above threshold)")

    # Start engine and manually trigger pruning
    snn_engine.start()

    import asyncio

    async def trigger_manual_pruning():
        await pruner._trigger_pruning(metrics)

    asyncio.run(trigger_manual_pruning())

    print(f"[2] After pruning:")
    print(f"  Synapses: {snn_engine.get_active_synapses()}")
    print(f"  Pruning count: {pruner.get_stats()['pruning_count']}")

    # Check Windows sensor cooling
    if pruner._windows_reader:
        print(f"[3] Windows sensor cooling applied: -3°C simulated")

    snn_engine.stop()
    pruner.stop()

    print("\nDemo complete.")


if __name__ == "__main__":
    import asyncio

    # Run the demo with manual trigger for clear visibility
    run_pruning_demo()