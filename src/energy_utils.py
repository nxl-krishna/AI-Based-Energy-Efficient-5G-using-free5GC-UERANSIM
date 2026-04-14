"""
energy_utils.py
---------------
Utility functions for reading real system energy via Intel RAPL.

On Linux with an Intel CPU this reads:
  /sys/class/powercap/intel-rapl:0/energy_uj

The value is a monotonically increasing counter in micro-joules.
Compute delta between two readings to get energy consumed over a window.
"""

import os
import logging
import time

logger = logging.getLogger(__name__)

# Path to the Intel RAPL energy counter (package-level, socket 0)
RAPL_ENERGY_PATH = "/sys/class/powercap/intel-rapl:0/energy_uj"


def get_energy_uj() -> int:
    """
    Read the raw RAPL energy counter in micro-joules.

    Returns:
        Integer micro-joule counter value, or -1 if unavailable.
    """
    try:
        with open(RAPL_ENERGY_PATH, "r") as f:
            return int(f.read().strip())
    except FileNotFoundError:
        logger.warning(
            "RAPL energy file not found. "
            "Ensure you are on a Linux machine with an Intel CPU and RAPL support. "
            f"Expected path: {RAPL_ENERGY_PATH}"
        )
        return -1
    except PermissionError:
        logger.warning(
            "Permission denied reading RAPL. "
            "Try: sudo chmod a+r /sys/class/powercap/intel-rapl:0/energy_uj"
        )
        return -1
    except Exception as e:
        logger.error(f"Unexpected error reading RAPL energy: {e}")
        return -1


def measure_energy_joules(duration_sec: float = 1.0) -> tuple:
    """
    Measure energy consumed over a given duration.

    Args:
        duration_sec: How many seconds to measure over.

    Returns:
        (energy_joules, power_watts) — both are 0.0 if RAPL unavailable.
    """
    start_uj = get_energy_uj()
    time.sleep(duration_sec)
    end_uj = get_energy_uj()

    if start_uj < 0 or end_uj < 0:
        return 0.0, 0.0

    # Handle RAPL counter rollover (counter resets at max_energy_uj)
    if end_uj < start_uj:
        logger.debug("RAPL counter rollover detected, skipping this sample.")
        return 0.0, 0.0

    energy_joules = (end_uj - start_uj) / 1_000_000.0  # µJ → J
    power_watts = energy_joules / duration_sec
    return energy_joules, power_watts


def rapl_available() -> bool:
    """Returns True if the RAPL energy file is readable."""
    return os.access(RAPL_ENERGY_PATH, os.R_OK)
