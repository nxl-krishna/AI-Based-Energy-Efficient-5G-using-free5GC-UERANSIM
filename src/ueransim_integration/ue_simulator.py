"""
ue_simulator.py
---------------
Generates UE traffic via docker exec into the ueransim-ue container.

All traffic commands (ping, iperf3) run inside the container so they
use the uesimtun0 tunnel interface created by nr-ue, not the host NIC.
"""

import logging
import subprocess
from typing import List, Optional
import sys
from pathlib import Path

# Make src/ importable when this module is run directly
if str(Path(__file__).parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent))

from docker_utils import docker_exec, is_container_running

logger = logging.getLogger(__name__)

# Name of the UE container (must match docker-compose.yaml)
UE_CONTAINER = "ueransim-ue"


class UESimulator:
    """
    Manages User Equipment traffic generation via docker exec.

    Traffic is generated inside the 'ueransim-ue' container so it flows
    through the uesimtun0 tunnel interface established by UERANSIM nr-ue.
    """

    def __init__(self):
        """
        No host-path configuration needed — all execution is via Docker.
        """
        # Tracks active background Popen handles (docker exec wrappers)
        self.active_traffic_procs: List[subprocess.Popen] = []

    def generate_traffic(
        self,
        interface: str = "uesimtun0",
        target_ip: str = "8.8.8.8",
        bandwidth_mbps: float = None,
    ) -> bool:
        """
        Generate traffic inside the ueransim-ue container.

        Args:
            interface:      TUN interface to bind to (default: uesimtun0).
            target_ip:      Destination IP address.
            bandwidth_mbps: If None → use ping (ICMP).
                            If set  → use iperf3 UDP at given Mbps.

        Returns:
            True if the background process was launched, False on error.
        """
        if not is_container_running(UE_CONTAINER):
            logger.error(
                f"Container '{UE_CONTAINER}' is not running. "
                "Start it first with UERANSIMController.start_ue()."
            )
            return False

        if bandwidth_mbps is None:
            # ICMP ping — lightweight background traffic
            cmd = ["ping", "-I", interface, "-i", "0.2", target_ip]
            logger.info(f"Generating ICMP traffic on {interface} → {target_ip} (inside {UE_CONTAINER})")
        else:
            # iperf3 UDP — bandwidth-controlled traffic
            # Requires an iperf3 server listening on target_ip
            bw_str = f"{bandwidth_mbps}M"
            cmd = [
                "iperf3", "-c", target_ip,
                "-u", "-b", bw_str,
                "-B", interface,
                "-t", "3600",   # run for 1 hour (stopped explicitly)
            ]
            logger.info(
                f"Generating iperf3 UDP traffic ({bandwidth_mbps} Mbps) "
                f"on {interface} → {target_ip} (inside {UE_CONTAINER})"
            )

        # Launch as background docker exec process
        proc = docker_exec(UE_CONTAINER, cmd, background=True)
        if proc is None:
            logger.error("Failed to launch traffic generation process.")
            return False

        self.active_traffic_procs.append(proc)
        return True

    def stop_traffic(self) -> None:
        """
        Stop all active traffic generation processes.

        Terminates the docker exec wrapper processes; the commands inside
        the container exit when the exec session is closed.
        """
        stopped = 0
        for proc in self.active_traffic_procs:
            if proc.poll() is None:  # still running
                proc.terminate()
                stopped += 1
        self.active_traffic_procs = []
        logger.info(f"Stopped {stopped} traffic generation process(es).")

    def active_count(self) -> int:
        """Return number of currently active traffic streams."""
        # Clean up finished processes first
        self.active_traffic_procs = [
            p for p in self.active_traffic_procs if p.poll() is None
        ]
        return len(self.active_traffic_procs)
