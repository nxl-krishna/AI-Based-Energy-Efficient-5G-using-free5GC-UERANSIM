"""
metrics_collector.py
--------------------
Collects UPF network throughput and real system energy (Intel RAPL).
"""

import logging
import time
from typing import Dict
import sys
from pathlib import Path

# Make src/ importable when this module is run directly
if str(Path(__file__).parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent))

from docker_utils import docker_exec, is_container_running
from energy_utils import get_energy_uj, rapl_available

logger = logging.getLogger(__name__)

UPF_CONTAINER = "upf"


class Free5GCMetricsCollector:
    def __init__(self, interface: str = "upfgtp"):
        self.interface = interface

        # Throughput tracking state
        self.last_rx: int = 0
        self.last_tx: int = 0
        self.last_time: float = 0.0

        if not rapl_available():
            logger.warning(
                "Intel RAPL not available. Energy readings will return 0."
            )

    # ------------------------------------------------------------------
    # Throughput
    # ------------------------------------------------------------------

    def collect_throughput(self) -> float:
        current_time = time.time()

        if not is_container_running(UPF_CONTAINER):
            logger.warning(f"UPF container '{UPF_CONTAINER}' is not running.")
            return 0.0

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
                if "RX:" in line and i + 1 < len(lines):
                    rx_bytes = int(lines[i + 1].split()[0])
                elif "TX:" in line and i + 1 < len(lines):
                    tx_bytes = int(lines[i + 1].split()[0])

            if rx_bytes is None or tx_bytes is None:
                raise ValueError("Could not find RX/TX bytes")

        except Exception as e:
            logger.error(f"Parsing failed: {e}\nOutput:\n{result.stdout}")
            return 0.0

        # First call — initialize
        if self.last_time == 0.0:
            self.last_rx = rx_bytes
            self.last_tx = tx_bytes
            self.last_time = current_time
            return 0.0

        # Handle counter reset (container restart / overflow)
        if rx_bytes < self.last_rx or tx_bytes < self.last_tx:
            logger.warning("Counter reset detected. Reinitializing counters.")
            self.last_rx = rx_bytes
            self.last_tx = tx_bytes
            self.last_time = current_time
            return 0.0

        dt = current_time - self.last_time
        if dt <= 0:
            return 0.0

        drx = rx_bytes - self.last_rx
        dtx = tx_bytes - self.last_tx

        # Update state
        self.last_rx = rx_bytes
        self.last_tx = tx_bytes
        self.last_time = current_time

        # Convert to Mbps
        total_mbps = ((drx + dtx) * 8.0) / 1_000_000.0 / dt
        return total_mbps

    # ------------------------------------------------------------------
    # Energy (RAPL)
    # ------------------------------------------------------------------

    def collect_energy(self, sample_window_sec: float = 1.0) -> Dict[str, float]:
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

        logger.debug(
            f"RAPL: {energy_joules:.4f} J over {sample_window_sec}s → {power_watts:.2f} W"
        )

        return {
            "energy_joules": energy_joules,
            "power_watts": power_watts,
        }