import subprocess
import os
import logging
import yaml
from pathlib import Path

logger = logging.getLogger(__name__)

class Free5GCController:
    """Controls the free5GC core network (via systemd or docker-compose)."""
    
    def __init__(self, config_file: str = None):
        self.deployment_type = "docker"
        self.docker_dir = "~/free5gc-compose"
        
        # Load configuration
        if config_file and Path(config_file).exists():
            with open(config_file, 'r') as f:
                config = yaml.safe_load(f)
                if config and 'free5gc' in config:
                    self.deployment_type = config['free5gc'].get('deployment_type', 'docker')
                    self.docker_dir = os.path.expanduser(config['free5gc'].get('docker_compose_dir', '~/free5gc-compose'))

    def check_core_status(self) -> bool:
        """Check if AMF and UPF are running."""
        if os.name == 'nt':
            return True # Mock for Windows
            
        try:
            if self.deployment_type == "docker":
                cmd = ["docker", "compose", "-f", os.path.join(self.docker_dir, "docker-compose.yaml"), "ps", "--services", "--filter", "status=running"]
                result = subprocess.run(cmd, capture_output=True, text=True)
                running_svcs = result.stdout.lower()
                return "amf" in running_svcs and "upf" in running_svcs
            else:
                # systemd
                result = subprocess.run(["systemctl", "is-active", "free5gc-amf"], capture_output=True, text=True)
                return "active" in result.stdout
        except Exception as e:
            logger.error(f"Failed to check free5gc status: {e}")
            return False

    def restart_upf(self) -> bool:
        """Restart the UPF network function (e.g., when clearing sessions abruptly)."""
        if os.name == 'nt':
            logger.info("Mock Windows UPF restart.")
            return True
            
        try:
            if self.deployment_type == "docker":
                cmd = ["docker", "compose", "-f", os.path.join(self.docker_dir, "docker-compose.yaml"), "restart", "upf"]
            else:
                cmd = ["sudo", "systemctl", "restart", "free5gc-upf"]
                
            subprocess.run(cmd, check=True)
            logger.info("UPF restarted successfully.")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to restart UPF: {e}")
            return False
