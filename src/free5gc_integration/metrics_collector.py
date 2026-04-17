"""
metrics_collector.py
--------------------
Collects UPF network throughput and real system energy (Intel RAPL).

Changes from original:
  - `ip -s link show upfgtp` now runs inside the "upf" Docker container
    via `docker exec upf ip -s link show upfgtp`
  - Added `collect_energy()` which returns current power in Watts using
    Intel RAPL counters, measured over a 1-second sampling window.
"""

import os
import logging
import time
from typing import Dict, Tuple
import sys
from pathlib import Path

# Make src/ importable when this module is run directly
if str(Path(__file__).parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent))

from docker_utils import docker_exec, is_container_running
from energy_utils import get_energy_uj, rapl_available

logger = logging.getLogger(__name__)

# Docker container name for free5GC UPF (must match docker-compose.yaml)
UPF_CONTAINER = "upf"


class Free5GCMetricsCollector:
    """
    Collects UPF throughput and RAPL-based energy metrics.

    Throughput — reads interface stats from inside the UPF container.
    Energy     — reads Intel RAPL counter delta over a sampling interval.
    """

    def __init__(self, interface: str = "upfgtp"):
        self.interface = interface

        # Throughput tracking state
        self.last_rx: int = 0
        self.last_tx: int = 0
        self.last_time: float = 0.0

        # RAPL availability warning (print once)
        if not rapl_available():
            logger.warning(
                "Intel RAPL not available on this machine. "
                "Energy readings will return 0. "
                "This is expected on Windows/non-Intel hosts during development."
            )

    # ------------------------------------------------------------------
    # Throughput
    # ------------------------------------------------------------------

    def collect_throughput(self) -> float:
        """
        Calculate UPF throughput in Mbps by reading interface stats
        from inside the UPF Docker container.

        Returns:
            Throughput in Mbps, or 0.0 on error.
        """
        current_time = time.time()

        if not is_container_running(UPF_CONTAINER):
            logger.warning(f"UPF container '{UPF_CONTAINER}' is not running.")
            return 0.0

        # Run: docker exec upf ip -s link show upfgtp
        result = docker_exec(
            UPF_CONTAINER,
            ["ip", "-s", "link", "show", self.interface],
            background=False,
        )

        if result is None or result.returncode != 0:
            logger.error(
                f"Failed to read interface '{self.interface}' stats from container '{UPF_CONTAINER}'."
            )
            return 0.0

        try:
            lines = result.stdout.splitlines()
            rx_bytes, tx_bytes = None, None

            for i, line in enumerate(lines):
                if "RX:" in line:
                    rx_bytes = int(lines[i + 1].split()[0])
                elif "TX:" in line:
                    tx_bytes = int(lines[i + 1].split()[0])

            if rx_bytes is None or tx_bytes is None:
                raise ValueError("Could not find RX/TX bytes")

        except Exception as e:
            logger.error(f"Failed to parse ip -s link output: {e}\nOutput:\n{result.stdout}")
            return 0.0

        # First call — seed the counters
        if self.last_time == 0.0:
            self.last_rx = rx_bytes
            self.last_tx = tx_bytes
            self.last_time = current_time
            return 0.0

        if rx_bytes < self.last_rx or tx_bytes < self.last_tx:
            self.last_rx = rx_bytes
            self.last_tx = tx_bytes
            self.last_time = current_time
            return 0.0

        dt = current_time - self.last_time
        if dt <= 0:
            return 0.0

        drx = max(0, rx_bytes - self.last_rx)
        dtx = max(0, tx_bytes - self.last_tx)

        self.last_rx = rx_bytes
        self.last_tx = tx_bytes
        self.last_time = current_time

        # (bytes * 8 bits) / 1_000_000 / seconds = Mbps
        total_mbps = ((drx + dtx) * 8.0) / 1_000_000.0 / dt
        return total_mbps

    # ------------------------------------------------------------------
    # Energy (RAPL)
    # ------------------------------------------------------------------

    def collect_energy(self, sample_window_sec: float = 1.0) -> Dict[str, float]:
        """
        Measure system-level energy using Intel RAPL over a short window.

        Args:
            sample_window_sec: Sampling duration in seconds (default 1s).
                               Longer windows give more accurate power readings.

        Returns:
            Dict with keys:
              'energy_joules' — energy consumed during the window
              'power_watts'   — average power during the window
        """
        start_uj = get_energy_uj()
        time.sleep(sample_window_sec)
        end_uj = get_energy_uj()

        if start_uj < 0 or end_uj < 0:
            return {"energy_joules": 0.0, "power_watts": 0.0}

        # Handle RAPL counter wrap-around
        if end_uj < start_uj:
            logger.debug("RAPL counter rollover — skipping sample.")
            return {"energy_joules": 0.0, "power_watts": 0.0}

        energy_joules = (end_uj - start_uj) / 1_000_000.0
        power_watts = energy_joules / sample_window_sec

        logger.debug(f"RAPL: {energy_joules:.4f} J over {sample_window_sec}s → {power_watts:.2f} W")
        return {"energy_joules": energy_joules, "power_watts": power_watts}

