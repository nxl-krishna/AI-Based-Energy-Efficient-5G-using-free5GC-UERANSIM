import os
import subprocess
import logging
import re
from typing import Dict, Tuple

logger = logging.getLogger(__name__)

class Free5GCMetricsCollector:
    """Scrapes UPF and OS telemetry."""
    
    def __init__(self, interface: str = "upfgtp"):
        self.interface = interface
        self.last_rx = 0
        self.last_tx = 0
        self.last_time = 0.0

    def collect_throughput(self) -> float:
        """
        Uses standard Linux `ip -s link` command to calculate throughput in Mbps.
        """
        if os.name == 'nt':
            import random
            return random.uniform(10, 50) # Mock on Windows
            
        import time
        current_time = time.time()
        
        try:
            cmd = ["ip", "-s", "link", "show", self.interface]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            # regex to parse rx/tx bytes 
            # ip -s output has Rx/Tx lines followed by stats
            lines = result.stdout.split('\n')
            rx_bytes_line = lines[3].strip().split()
            tx_bytes_line = lines[5].strip().split()
            
            rx_bytes = int(rx_bytes_line[0])
            tx_bytes = int(tx_bytes_line[0])
            
            if self.last_time == 0:
                self.last_rx = rx_bytes
                self.last_tx = tx_bytes
                self.last_time = current_time
                return 0.0
                
            dt = current_time - self.last_time
            if dt == 0: dt = 1
            
            drx = rx_bytes - self.last_rx
            dtx = tx_bytes - self.last_tx
            
            self.last_rx = rx_bytes
            self.last_tx = tx_bytes
            self.last_time = current_time
            
            # Output in Mbps: (Bytes * 8) / (1_000_000) / seconds
            total_mbps = ((drx + dtx) * 8.0) / 1_000_000.0 / dt
            return total_mbps
            
        except Exception as e:
            logger.error(f"Failed to read interface {self.interface} stats: {e}")
            return 0.0
