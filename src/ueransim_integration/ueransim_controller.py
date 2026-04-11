import os
import subprocess
import logging
import yaml
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

class UERANSIMController:
    """Controls the actual nr-gnb instances on Linux."""
    
    def __init__(self, config_file: str = None):
        self.config = {
            'ueransim': {
                'bin_path': '~/UERANSIM/build',
                'config_path': '~/UERANSIM/config'
            }
        }
        
        # Load configuration
        if config_file and Path(config_file).exists():
            with open(config_file, 'r') as f:
                loaded_config = yaml.safe_load(f)
                if loaded_config and 'ueransim' in loaded_config:
                    self.config['ueransim'].update(loaded_config['ueransim'])

        self.bin_path = os.path.expanduser(self.config['ueransim']['bin_path'])
        self.config_dir = os.path.expanduser(self.config['ueransim']['config_path'])
        
        # Cache of running processes: bs_id -> Popen object
        self.running_gnbs = {}
        
    def start_gnb(self, bs_id: int, config_filename: str):
        """Starts a specific gNodeB process using UERANSIM"""
        if os.name == 'nt':
            logger.warning("Windows OS detected. Mocking start_gnb command.")
            self.running_gnbs[bs_id] = "mock_process"
            return True
            
        if bs_id in self.running_gnbs:
            logger.info(f"gNB '{bs_id}' is already running.")
            return True
            
        executable = os.path.join(self.bin_path, "nr-gnb")
        cfg_path = os.path.join(self.config_dir, config_filename)
        
        if not os.path.exists(executable):
            logger.error(f"Cannot find nr-gnb executable at {executable}")
            return False
            
        cmd = [executable, "-c", cfg_path]
        logger.info(f"Starting gNB {bs_id}: {' '.join(cmd)}")
        
        try:
            # Run detached process
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.running_gnbs[bs_id] = proc
            return True
        except Exception as e:
            logger.error(f"Failed to start gNB {bs_id}: {e}")
            return False

    def stop_gnb(self, bs_id: int):
        """Stops a specific running gNodeB"""
        if os.name == 'nt':
            logger.warning(f"Windows OS detected. Mocking stop_gnb command for {bs_id}.")
            if bs_id in self.running_gnbs:
                del self.running_gnbs[bs_id]
            return True
            
        if bs_id not in self.running_gnbs:
            logger.warning(f"gNB {bs_id} is not currently tracked as running.")
            return False
            
        proc = self.running_gnbs[bs_id]
        if isinstance(proc, subprocess.Popen):
            logger.info(f"Terminating gNB {bs_id} (PID: {proc.pid})")
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        
        del self.running_gnbs[bs_id]
        return True
        
    def get_active_gnbs(self) -> List[int]:
        """Returns list of active Base Station IDs."""
        return list(self.running_gnbs.keys())
