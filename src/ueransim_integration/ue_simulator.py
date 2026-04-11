import os
import subprocess
import logging
import time

logger = logging.getLogger(__name__)

class UESimulator:
    """Manages User Equipment using UERANSIM nr-ue"""
    
    def __init__(self, bin_path: str = "~/UERANSIM/build", config_dir: str = "~/UERANSIM/config"):
        self.bin_path = os.path.expanduser(bin_path)
        self.config_dir = os.path.expanduser(config_dir)
        self.active_ping_procs = []
        
    def generate_traffic(self, interface: str = "uesimtun0", target_ip: str = "8.8.8.8", bandwidth_mbps: float = None):
        """
        Generates simulated traffic across the UE tun interface.
        If bandwidth_mbps is None, uses ping. If specified, uses iperf3.
        """
        if os.name == 'nt':
            logger.warning("Windows OS detected. Mocking UE traffic generation.")
            return True
            
        try:
            if bandwidth_mbps is None:
                # Generate background ICMP ping trace
                cmd = ["ping", "-I", interface, "-i", "0.2", target_ip]
                logger.info(f"Generating ICMP traffic on {interface}")
                proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.active_ping_procs.append(proc)
            else:
                # Generate iperf3 UDP workload
                # Note: requires an iperf3 server listening on target_ip
                bw_str = f"{bandwidth_mbps}M"
                cmd = ["iperf3", "-c", target_ip, "-u", "-b", bw_str, "-B", interface, "-t", "3600"]
                logger.info(f"Generating iperf3 traffic: {bandwidth_mbps} Mbps on {interface}")
                proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.active_ping_procs.append(proc)
            return True
        except Exception as e:
            logger.error(f"Traffic generation failed: {e}")
            return False
            
    def stop_traffic(self):
        """Stops all active traffic generation streams."""
        for proc in self.active_ping_procs:
            if proc.poll() is None: # still running
                proc.terminate()
        self.active_ping_procs = []
        logger.info("Stopped all generated traffic.")
