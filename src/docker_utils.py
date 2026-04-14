"""
docker_utils.py
---------------
Reusable Docker helper functions for controlling containers and
executing commands inside them.

All long-running services (gNB, UE) are managed via docker compose.
Short-lived commands (ping, iperf3, ip stats) use docker exec.
"""

import subprocess
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

# Default docker compose project directory (where docker-compose.yaml lives)
# Override by setting COMPOSE_PROJECT_DIR before importing, or pass explicitly.
import os
COMPOSE_PROJECT_DIR = os.environ.get("COMPOSE_PROJECT_DIR", ".")


def run_docker_command(cmd: List[str], cwd: str = None, timeout: int = 30) -> subprocess.CompletedProcess:
    """
    Run a docker or docker compose command and return the result.

    Args:
        cmd:     Full command list, e.g. ["docker", "compose", "up", "-d", "ueransim-gnb"]
        cwd:     Working directory (defaults to COMPOSE_PROJECT_DIR)
        timeout: Seconds to wait before raising TimeoutExpired

    Returns:
        CompletedProcess with .returncode, .stdout, .stderr
    """
    cwd = cwd or COMPOSE_PROJECT_DIR
    logger.debug(f"Running docker command: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            logger.warning(
                f"Docker command exited {result.returncode}: {' '.join(cmd)}\n"
                f"stderr: {result.stderr.strip()}"
            )
        return result
    except subprocess.TimeoutExpired:
        logger.error(f"Docker command timed out after {timeout}s: {' '.join(cmd)}")
        raise
    except Exception as e:
        logger.error(f"Docker command failed: {e}")
        raise


def docker_exec(container: str, command: List[str], background: bool = False) -> Optional[subprocess.Popen]:
    """
    Execute a command inside a running container.

    Args:
        container:  Container name, e.g. "ueransim-ue"
        command:    Command to run, e.g. ["ping", "-I", "uesimtun0", "8.8.8.8"]
        background: If True, returns a Popen handle (non-blocking).
                    If False, blocks until command completes and returns None.

    Returns:
        Popen handle if background=True, else None.
    """
    full_cmd = ["docker", "exec", container] + command
    logger.debug(f"docker exec [{container}]: {' '.join(command)}")

    if background:
        try:
            proc = subprocess.Popen(
                full_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return proc
        except Exception as e:
            logger.error(f"Background docker exec failed for {container}: {e}")
            return None
    else:
        try:
            result = subprocess.run(
                full_cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result
        except Exception as e:
            logger.error(f"docker exec failed for {container}: {e}")
            return None


def is_container_running(container_name: str) -> bool:
    """
    Check whether a container is currently running.

    Uses `docker inspect` to query the container's running state.

    Args:
        container_name: Name of the container to check.

    Returns:
        True if running, False otherwise.
    """
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Running}}", container_name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip() == "true"
    except Exception as e:
        logger.error(f"Failed to inspect container '{container_name}': {e}")
        return False
