"""
Traffic Monitoring Module
Collects real-time metrics from UERANSIM and free5GC

Changes from original:
  - Energy is now measured via Intel RAPL (energy_utils) instead of a
    CPU-load formula.  The RAPL counter is read before and after each
    sampling window; the delta gives real Joules consumed.
  - collect_metrics() returns, and get_recent_metrics() exports, a
    DataFrame with the standardised columns:
        UE, Throughput, CPU, Memory, Energy
  - Feature engineering columns added:
        CPU_per_UE        = CPU  / UE_count
        Throughput_per_UE = Throughput / UE_count
  - Free5GCMetricsCollector is used for real throughput (Docker-based).
"""

import os
import sys
import time
import psutil
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# TrafficMetric dataclass
# ---------------------------------------------------------------------------

@dataclass
class TrafficMetric:
    """Data class for traffic metrics at a specific timestamp."""
    timestamp: datetime
    active_users: int
    total_data_mbps: float
    average_latency_ms: float
    throughput_mbps: float
    packet_loss_rate: float
    energy_consumption_w: float       # Real RAPL-measured power (watts)
    energy_joules: float              # Energy consumed during collection window (J)
    cpu_percent: float                # Host CPU utilisation %
    memory_percent: float             # Host memory utilisation %
    active_base_stations: int

    # Per-BS metrics (kept for compatibility with decision engine)
    bs_loads:  Dict[int, float] = field(default_factory=dict)  # BS_ID → Load %
    bs_energy: Dict[int, float] = field(default_factory=dict)  # BS_ID → Power (W)


# ---------------------------------------------------------------------------
# Imports for real Linux collectors
# ---------------------------------------------------------------------------

if str(Path(__file__).parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from free5gc_integration.metrics_collector import Free5GCMetricsCollector
    from ueransim_integration.ue_simulator import UESimulator
    from energy_utils import get_energy_uj, rapl_available
    HAS_LINUX_MODS = True
except ImportError:
    HAS_LINUX_MODS = False


# ---------------------------------------------------------------------------
# TrafficMonitor
# ---------------------------------------------------------------------------

class TrafficMonitor:
    """
    Real-time traffic monitoring system.
    Collects metrics from UERANSIM and free5GC.

    Energy measurement strategy:
      1. Read RAPL counter at start of collection.
      2. Collect other metrics (throughput, CPU, memory).
      3. Read RAPL counter at end.
      4. Compute energy_joules = (end - start) / 1e6
                 power_watts   = energy_joules / elapsed_seconds
      Fallback: if RAPL is unavailable (non-Intel / Windows), power = 0.
    """

    def __init__(self, collection_interval_sec: int = 60, num_bs: int = 10):
        self.collection_interval = collection_interval_sec
        self.num_base_stations   = num_bs
        self.metrics_history: List[TrafficMetric] = []
        self.start_time = datetime.now()

        # Initialise real collectors if on Linux with the required modules
        self.use_real_linux = HAS_LINUX_MODS and os.name != "nt"
        if self.use_real_linux:
            self.free5gc_metrics = Free5GCMetricsCollector()
            self.ue_simulator    = UESimulator()
            self._rapl_ok        = rapl_available()
            logger.info("Initialised real Linux telemetry collectors.")
            if not self._rapl_ok:
                logger.warning("RAPL not available — energy readings will be 0.")
        else:
            self._rapl_ok = False
            logger.info("Initialising mock telemetry simulation (non-Linux or missing modules).")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _read_rapl_uj(self) -> int:
        """Read RAPL counter; returns -1 if unavailable."""
        if not self._rapl_ok:
            return -1
        return get_energy_uj()

    def _get_cpu_memory(self) -> tuple:
        """Return (cpu_percent, memory_percent) using psutil."""
        try:
            cpu_pct = psutil.cpu_percent(interval=None)
            mem_pct = psutil.virtual_memory().percent
            return cpu_pct, mem_pct
        except Exception:
            return 0.0, 0.0

    # ------------------------------------------------------------------
    # Metric collection
    # ------------------------------------------------------------------

    def collect_ueransim_metrics(self) -> Dict:
        """Collect UERANSIM metrics (simulated traffic patterns)."""
        current_hour = datetime.now().hour

        if 18 <= current_hour <= 22:          # Peak hours
            active_users = np.random.randint(400, 500)
            data_rate    = np.random.uniform(30, 50)
            latency      = np.random.uniform(15, 25)
        elif 1 <= current_hour <= 6:          # Off-peak hours
            active_users = np.random.randint(50, 100)
            data_rate    = np.random.uniform(1, 5)
            latency      = np.random.uniform(5, 10)
        else:                                  # Shoulder hours
            active_users = np.random.randint(150, 300)
            data_rate    = np.random.uniform(10, 25)
            latency      = np.random.uniform(10, 18)

        return {
            "active_users":      active_users,
            "total_data_mbps":   data_rate,
            "average_latency_ms": latency,
            "packet_loss_rate":  np.random.uniform(0.0001, 0.001),
        }

    def collect_free5gc_metrics(self) -> Dict:
        """Collect free5GC UPF metrics (real throughput via docker exec if available)."""
        if self.use_real_linux:
            throughput = self.free5gc_metrics.collect_throughput()
            return {
                "throughput_mbps":       throughput,
                "active_sessions":       int(throughput * 2.5),
                "amf_response_time_ms":  np.random.uniform(10, 50),
                "smf_response_time_ms":  np.random.uniform(5, 20),
            }

        # Mock: derive from UERANSIM data
        ueransim_data = self.collect_ueransim_metrics()
        throughput    = ueransim_data["total_data_mbps"] * 0.95
        return {
            "throughput_mbps":       throughput,
            "active_sessions":       int(ueransim_data["active_users"] * 2.5),
            "amf_response_time_ms":  np.random.uniform(10, 50),
            "smf_response_time_ms":  np.random.uniform(5, 20),
        }

    def calculate_bs_metrics(self, total_users: int, measured_power_w: float) -> tuple:
        """
        Calculate per-base-station load and energy distribution.

        Energy is now distributed from the real measured system power
        instead of being computed from a CPU formula.
        """
        bs_loads  = {}
        bs_energy = {}

        for bs_id in range(1, self.num_base_stations + 1):
            users_per_bs    = np.random.randint(0, max(1, total_users // self.num_base_stations))
            load_percentage = min(1.0, users_per_bs / 100.0)
            bs_loads[bs_id] = load_percentage * 100

        # Distribute measured power proportional to load
        total_load = sum(bs_loads.values()) or 1.0
        for bs_id, load in bs_loads.items():
            bs_energy[bs_id] = (load / total_load) * measured_power_w

        return bs_loads, bs_energy

    def collect_metrics(self) -> TrafficMetric:
        """
        Collect all metrics for one time-step.

        RAPL energy measurement wraps the collection window:
          1. Record energy_start (µJ)
          2. Collect throughput, CPU, memory
          3. Record energy_end   (µJ)
          4. Compute real energy and power
        """
        t_start   = time.time()
        rapl_start = self._read_rapl_uj()

        # --- Collect network and system metrics ---
        ueransim_data = self.collect_ueransim_metrics()
        free5gc_data  = self.collect_free5gc_metrics()
        cpu_pct, mem_pct = self._get_cpu_memory()

        rapl_end = self._read_rapl_uj()
        t_end    = time.time()

        # --- Compute energy from RAPL delta ---
        elapsed = t_end - t_start or 1.0

        if rapl_start >= 0 and rapl_end >= 0 and rapl_end >= rapl_start:
            # Real measurement path
            energy_joules = (rapl_end - rapl_start) / 1_000_000.0  # µJ → J
            power_watts   = energy_joules / elapsed
        else:
            # Fallback: RAPL unavailable (Windows / non-Intel)
            energy_joules = 0.0
            power_watts   = 0.0

        total_users = ueransim_data["active_users"]
        bs_loads, bs_energy = self.calculate_bs_metrics(total_users, power_watts)
        active_bs = sum(1 for e in bs_energy.values() if e > 0)

        metric = TrafficMetric(
            timestamp             = datetime.now(),
            active_users          = total_users,
            total_data_mbps       = ueransim_data["total_data_mbps"],
            average_latency_ms    = ueransim_data["average_latency_ms"],
            throughput_mbps       = free5gc_data["throughput_mbps"],
            packet_loss_rate      = ueransim_data["packet_loss_rate"],
            energy_consumption_w  = power_watts,   # Real RAPL-derived watts
            energy_joules         = energy_joules,
            cpu_percent           = cpu_pct,
            memory_percent        = mem_pct,
            active_base_stations  = active_bs,
            bs_loads              = bs_loads,
            bs_energy             = bs_energy,
        )

        self.metrics_history.append(metric)
        return metric

    # ------------------------------------------------------------------
    # Data export
    # ------------------------------------------------------------------

    def get_recent_metrics(self, duration_minutes: int = 60) -> pd.DataFrame:
        """
        Return metrics from the last N minutes as a DataFrame.

        Columns (CSV-ready format):
            UE, Throughput, CPU, Memory, Energy,
            CPU_per_UE (feature engineering),
            Throughput_per_UE (feature engineering)
        """
        cutoff_time = datetime.now() - timedelta(minutes=duration_minutes)
        recent = [m for m in self.metrics_history if m.timestamp >= cutoff_time]

        if not recent:
            return pd.DataFrame()

        df = pd.DataFrame({
            "timestamp":       [m.timestamp          for m in recent],
            "UE":              [m.active_users        for m in recent],
            "Throughput":      [m.throughput_mbps     for m in recent],
            "CPU":             [m.cpu_percent         for m in recent],
            "Memory":          [m.memory_percent      for m in recent],
            "Energy":          [m.energy_consumption_w for m in recent],
            "energy_joules":   [m.energy_joules       for m in recent],
            "latency_ms":      [m.average_latency_ms  for m in recent],
            "pkt_loss_rate":   [m.packet_loss_rate    for m in recent],
            "active_bs":       [m.active_base_stations for m in recent],
        })

        # Feature engineering: per-UE normalised metrics
        df["CPU_per_UE"]        = df["CPU"]        / df["UE"].replace(0, 1)
        df["Throughput_per_UE"] = df["Throughput"] / df["UE"].replace(0, 1)

        return df

    def get_average_metrics(self, duration_minutes: int = 60) -> Dict:
        """Calculate average metrics over a period."""
        df = self.get_recent_metrics(duration_minutes)

        if df.empty:
            return {}

        return {
            "avg_users":         df["UE"].mean(),
            "avg_throughput":    df["Throughput"].mean(),
            "avg_energy_w":      df["Energy"].mean(),
            "avg_cpu":           df["CPU"].mean(),
            "avg_memory":        df["Memory"].mean(),
            "peak_users":        df["UE"].max(),
            "peak_energy_w":     df["Energy"].max(),
        }

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------

    def print_summary(self):
        """Print current traffic summary."""
        if not self.metrics_history:
            print("No metrics collected yet")
            return

        latest = self.metrics_history[-1]
        avg    = self.get_average_metrics(60)

        print("\n" + "=" * 60)
        print("TRAFFIC MONITORING SUMMARY")
        print("=" * 60)
        print(f"Timestamp:       {latest.timestamp}")
        print(f"\nCurrent Metrics:")
        print(f"  Active UEs:    {latest.active_users}")
        print(f"  Throughput:    {latest.throughput_mbps:.2f} Mbps")
        print(f"  CPU:           {latest.cpu_percent:.1f} %")
        print(f"  Memory:        {latest.memory_percent:.1f} %")
        print(f"  Energy:        {latest.energy_consumption_w:.2f} W  ({latest.energy_joules:.4f} J)")
        print(f"  Active BS:     {latest.active_base_stations}/{self.num_base_stations}")
        print(f"\n60-Minute Averages:")
        print(f"  Avg UEs:       {avg.get('avg_users', 0):.0f}")
        print(f"  Avg Energy:    {avg.get('avg_energy_w', 0):.2f} W")
        print(f"  Peak Energy:   {avg.get('peak_energy_w', 0):.2f} W")
        print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    monitor = TrafficMonitor()

    for i in range(5):
        metric = monitor.collect_metrics()
        print(
            f"[{i+1}] UEs={metric.active_users}  "
            f"Throughput={metric.throughput_mbps:.1f} Mbps  "
            f"CPU={metric.cpu_percent:.1f}%  "
            f"Mem={metric.memory_percent:.1f}%  "
            f"Energy={metric.energy_consumption_w:.2f} W"
        )

    monitor.print_summary()
    print("\nRecent metrics DataFrame head:")
    print(monitor.get_recent_metrics().head())
