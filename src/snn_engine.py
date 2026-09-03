"""
Spiking Neural Network (SNN) engine for cyber-physical power management.
Simulates computational workload with sparse tensor operations.
"""

import asyncio
import threading
import time
from typing import Optional

import torch


class SNNEngine:
    """
    Asynchronous SNN engine with continuous execution loop.
    Thread-safe controls for pause/resume and weight inspection.
    """

    def __init__(
        self,
        input_size: int = 256,
        hidden_sizes: list[int] = [512, 256, 128],
        output_size: int = 64,
        sparsity: float = 0.85,
    ):
        self.input_size = input_size
        self.hidden_sizes = hidden_sizes
        self.output_size = output_size
        self.sparsity = sparsity

        # Network architecture
        self.layer_sizes = [input_size] + hidden_sizes + [output_size]
        self.weights: list[torch.Tensor] = []
        self.biases: list[torch.Tensor] = []

        # Execution control
        self._lock = threading.RLock()
        self._running = False
        self._paused = False
        self._loop_task: Optional[asyncio.Task] = None

        # Statistics
        self._iterations = 0
        self._total_processing_time = 0.0

        # Initialize weights with sparse tensors
        self._initialize_weights()

    def _initialize_weights(self) -> None:
        """Initialize sparse synaptic weight matrices."""
        torch.manual_seed(42)

        for i in range(len(self.layer_sizes) - 1):
            in_size = self.layer_sizes[i]
            out_size = self.layer_sizes[i + 1]

            # Create sparse random weights
            # For matrix multiplication: output = weight.T @ input (column vector)
            # So weight should be (out_size, in_size) to multiply with input (in_size, 1)
            density = 1.0 - self.sparsity
            num_elements = int(in_size * out_size * density)
            
            # Generate random indices for sparse tensor
            # Row = output dimension, Col = input dimension
            row_indices = torch.randint(0, out_size, (num_elements,))
            col_indices = torch.randint(0, in_size, (num_elements,))
            values = torch.randn(num_elements) * 0.1
            
            indices = torch.stack([row_indices, col_indices])

            weight = torch.sparse_coo_tensor(
                indices=indices,
                values=values,
                size=(out_size, in_size),
            ).coalesce()

            self.weights.append(weight)
            self.biases.append(torch.zeros(out_size))

    async def _execution_loop(self, interval_ms: int = 10) -> None:
        """
        Continuous execution loop running matrix operations.
        Non-blocking with configurable interval.
        """
        while self._running:
            if not self._paused:
                start_time = time.time()

                # Simulate SNN processing
                await self._forward_pass()

                processing_time = time.time() - start_time
                self._total_processing_time += processing_time
                self._iterations += 1

            try:
                await asyncio.sleep(interval_ms / 1000.0)
            except asyncio.CancelledError:
                break

    async def _forward_pass(self) -> None:
        """Execute one forward pass through the network."""
        # Simulate input spikes
        with torch.no_grad():
            # Start with input layer spikes as column vector
            input_spike = (torch.rand(self.input_size) > 0.9).float().unsqueeze(1)

            for weight in self.weights:
                # Sparse matrix multiplication: weight @ input
                # weight shape: (in_size, out_size), input shape: (in_size, 1)
                # result shape: (out_size, 1)
                output = torch.sparse.mm(weight, input_spike)

                # Apply ReLU and threshold for spiking
                output = torch.relu(output)
                input_spike = output * (output > 0.5).float()

    def start(self) -> None:
        """Start the execution loop in background."""
        if self._running:
            return

        self._running = True
        self._paused = False

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        self._loop_task = loop.create_task(self._execution_loop())

        def run_loop():
            loop.run_until_complete(self._loop_task)

        self._thread = threading.Thread(target=run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the execution loop gracefully."""
        if not self._running:
            return

        self._running = False

        if self._loop_task:
            self._loop_task.cancel()

        if hasattr(self, "_thread") and self._thread.is_alive():
            self._thread.join(timeout=2.0)

    def pause(self) -> bool:
        """Pause the execution loop. Returns True if successfully paused."""
        with self._lock:
            if not self._running:
                return False
            self._paused = True
            return True

    def resume(self) -> bool:
        """Resume the execution loop. Returns True if successfully resumed."""
        with self._lock:
            if not self._running:
                return False
            self._paused = False
            return True

    def get_active_synapses(self) -> int:
        """
        Thread-safe method to count non-zero synaptic weights.

        Returns:
            Count of active (non-zero) synapses across all layers.
        """
        with self._lock:
            total = 0
            for weight in self.weights:
                # For sparse tensors, count actual stored values
                if weight.is_sparse:
                    total += weight._nnz()
                else:
                    total += (weight != 0).sum().item()
            return total

    def get_layer_stats(self) -> list[dict]:
        """Get statistics for each layer."""
        stats = []
        with self._lock:
            for i, weight in enumerate(self.weights):
                if weight.is_sparse:
                    nnz = weight._nnz()
                    size = weight.numel()
                else:
                    nnz = (weight != 0).sum().item()
                    size = weight.numel()

                stats.append({
                    "layer": i,
                    "input_size": self.layer_sizes[i],
                    "output_size": self.layer_sizes[i + 1],
                    "total_connections": size,
                    "active_synapses": nnz,
                    "sparsity": 1.0 - (nnz / size) if size > 0 else 0.0,
                })
        return stats

    def get_runtime_stats(self) -> dict:
        """Get execution statistics."""
        with self._lock:
            return {
                "running": self._running,
                "paused": self._paused,
                "iterations": self._iterations,
                "total_processing_time_s": round(self._total_processing_time, 3),
                "avg_processing_per_iter_ms": round(
                    (self._total_processing_time / self._iterations * 1000)
                    if self._iterations > 0
                    else 0,
                    3,
                ),
            }


def main():
    """Main entry point for direct execution."""
    print("=" * 60)
    print("Spiking Neural Network Engine")
    print("=" * 60)

    # Initialize engine
    engine = SNNEngine(
        input_size=256,
        hidden_sizes=[512, 256, 128],
        output_size=64,
        sparsity=0.85,
    )

    print(f"\nArchitecture: {engine.layer_sizes}")
    print(f"Initial active synapses: {engine.get_active_synapses()}")
    print(f"Layer stats: {engine.get_layer_stats()}")

    # Start execution
    print("\nStarting execution loop...")
    engine.start()

    try:
        while True:
            active = engine.get_active_synapses()
            stats = engine.get_runtime_stats()
            print(
                f"[{time.strftime('%H:%M:%S')}] "
                f"Active Synapses: {active:>6} | "
                f"Iterations: {stats['iterations']:>5} | "
                f"Avg Time: {stats['avg_processing_per_iter_ms']:>6.3f}ms"
            )
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping engine...")
        engine.stop()
        print("Done.")


if __name__ == "__main__":
    main()