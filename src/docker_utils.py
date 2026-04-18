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

# Default docker compose project directory
import os
COMPOSE_PROJECT_DIR = os.path.expanduser(os.environ.get("COMPOSE_PROJECT_DIR", "."))


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


def docker_exec(container: str, command: List[str], background: bool = False, cwd: str = None) -> Optional[subprocess.Popen]:
    """
    Execute a command inside a running container using docker compose.

    Args:
        container:  Service name, e.g. "ueransim-ue" or "upf"
        command:    Command to run, e.g. ["ping", "-I", "uesimtun0", "8.8.8.8"]
        background: If True, returns a Popen handle (non-blocking).
                    If False, blocks until command completes and returns None.
        cwd:        Working directory containing docker-compose.yml
    """
    cwd = cwd or COMPOSE_PROJECT_DIR
    full_cmd = ["docker", "compose", "exec", "-T", container] + command
    logger.debug(f"docker compose exec [{container}]: {' '.join(command)}")

    if background:
        try:
            proc = subprocess.Popen(
                full_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=cwd
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
                cwd=cwd
            )
            return result
        except Exception as e:
            logger.error(f"docker exec failed for {container}: {e}")
            return None


def is_container_running(container_name: str, cwd: str = None) -> bool:
    """
    Check whether a service is currently running.

    Uses `docker compose ps` to query the service's running state.
    """
    cwd = cwd or COMPOSE_PROJECT_DIR
    try:
        result = subprocess.run(
            ["docker", "compose", "ps", "--services", "--filter", "status=running"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return container_name in result.stdout.splitlines()
    except Exception as e:
        logger.error(f"Failed to check if service '{container_name}' is running: {e}")
        return False
