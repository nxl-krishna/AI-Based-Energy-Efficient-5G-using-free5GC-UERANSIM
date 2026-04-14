"""
ueransim_controller.py
----------------------
Controls UERANSIM gNB and UE via Docker compose.

Architecture:
  - "ueransim-gnb"  container runs nr-gnb
  - "ueransim-ue"   container runs nr-ue

Both containers are managed independently via `docker compose up/stop`.
No host-level UERANSIM binaries or config paths are needed.
"""

import logging
from typing import List
import sys
from pathlib import Path

# Make src/ importable when this module is run directly
if str(Path(__file__).parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent))

from docker_utils import run_docker_command, is_container_running

logger = logging.getLogger(__name__)

# Docker compose service names (must match docker-compose.yaml)
GNB_SERVICE = "ueransim-gnb"
UE_SERVICE  = "ueransim-ue"


class UERANSIMController:
    """
    Controls UERANSIM gNB and UE containers via docker compose.

    gNB and UE are managed independently so they can be started/stopped
    in any order required by the simulation.
    """

    def __init__(self, compose_dir: str = "."):
        """
        Args:
            compose_dir: Directory containing docker-compose.yaml.
                         Defaults to current working directory.
                         Override with the absolute path on your Linux host,
                         e.g. "/home/user/AI-5g-project"
        """
        self.compose_dir = compose_dir
        logger.info(f"UERANSIMController initialised (compose_dir={compose_dir})")

    # ------------------------------------------------------------------
    # gNB control
    # ------------------------------------------------------------------

    def start_gnb(self, bs_id: int = 0, config_filename: str = None) -> bool:
        """
        Start the gNB container.

        Args:
            bs_id:           Unused (kept for API compatibility with old controller).
            config_filename: Unused (config is baked into the container image).

        Returns:
            True on success, False on failure.
        """
        if is_container_running(GNB_SERVICE):
            logger.info(f"gNB container '{GNB_SERVICE}' is already running.")
            return True

        logger.info(f"Starting gNB container: {GNB_SERVICE}")
        result = run_docker_command(
            ["docker", "compose", "up", "-d", GNB_SERVICE],
            cwd=self.compose_dir,
        )
        success = result.returncode == 0
        if success:
            logger.info(f"gNB container '{GNB_SERVICE}' started successfully.")
        else:
            logger.error(f"Failed to start gNB container '{GNB_SERVICE}'.")
        return success

    def stop_gnb(self, bs_id: int = 0) -> bool:
        """
        Stop the gNB container.

        Args:
            bs_id: Unused (kept for API compatibility).

        Returns:
            True on success, False on failure.
        """
        if not is_container_running(GNB_SERVICE):
            logger.warning(f"gNB container '{GNB_SERVICE}' is not running.")
            return True  # Already stopped — not an error

        logger.info(f"Stopping gNB container: {GNB_SERVICE}")
        result = run_docker_command(
            ["docker", "compose", "stop", GNB_SERVICE],
            cwd=self.compose_dir,
        )
        success = result.returncode == 0
        if success:
            logger.info(f"gNB container '{GNB_SERVICE}' stopped.")
        else:
            logger.error(f"Failed to stop gNB container '{GNB_SERVICE}'.")
        return success

    # ------------------------------------------------------------------
    # UE control
    # ------------------------------------------------------------------

    def start_ue(self) -> bool:
        """
        Start the UE container (nr-ue).

        Returns:
            True on success, False on failure.
        """
        if is_container_running(UE_SERVICE):
            logger.info(f"UE container '{UE_SERVICE}' is already running.")
            return True

        logger.info(f"Starting UE container: {UE_SERVICE}")
        result = run_docker_command(
            ["docker", "compose", "up", "-d", UE_SERVICE],
            cwd=self.compose_dir,
        )
        success = result.returncode == 0
        if success:
            logger.info(f"UE container '{UE_SERVICE}' started successfully.")
        else:
            logger.error(f"Failed to start UE container '{UE_SERVICE}'.")
        return success

    def stop_ue(self) -> bool:
        """
        Stop the UE container.

        Returns:
            True on success, False on failure.
        """
        if not is_container_running(UE_SERVICE):
            logger.warning(f"UE container '{UE_SERVICE}' is not running.")
            return True  # Already stopped

        logger.info(f"Stopping UE container: {UE_SERVICE}")
        result = run_docker_command(
            ["docker", "compose", "stop", UE_SERVICE],
            cwd=self.compose_dir,
        )
        success = result.returncode == 0
        if success:
            logger.info(f"UE container '{UE_SERVICE}' stopped.")
        else:
            logger.error(f"Failed to stop UE container '{UE_SERVICE}'.")
        return success

    # ------------------------------------------------------------------
    # Status helpers
    # ------------------------------------------------------------------

    def get_active_gnbs(self) -> List[int]:
        """
        Returns [0] if the gNB container is running, [] otherwise.
        (Kept as List[int] for API compatibility with old controller.)
        """
        return [0] if is_container_running(GNB_SERVICE) else []

    def is_gnb_running(self) -> bool:
        """Check if the gNB container is up."""
        return is_container_running(GNB_SERVICE)

    def is_ue_running(self) -> bool:
        """Check if the UE container is up."""
        return is_container_running(UE_SERVICE)
