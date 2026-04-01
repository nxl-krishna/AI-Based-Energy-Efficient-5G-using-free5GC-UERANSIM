"""
Traffic Monitoring Module
Collects real-time metrics from UERANSIM and free5GC
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TrafficMetric:
    """Data class for traffic metrics at a specific timestamp"""
    timestamp: datetime
    active_users: int
    total_data_mbps: float
    average_latency_ms: float
    throughput_mbps: float
    packet_loss_rate: float
    energy_consumption_w: float
    active_base_stations: int
    
    # Per BS metrics
    bs_loads: Dict[int, float] = field(default_factory=dict)  # BS_ID -> Load %
    bs_energy: Dict[int, float] = field(default_factory=dict)  # BS_ID -> Power (W)


class TrafficMonitor:
    """
    Real-time traffic monitoring system
    Collects metrics from UERANSIM and free5GC
    """
    
    def __init__(self, collection_interval_sec: int = 60, num_bs: int = 10):
        self.collection_interval = collection_interval_sec
        self.num_base_stations = num_bs
        self.metrics_history: List[TrafficMetric] = []
        self.start_time = datetime.now()
        
    def collect_ueransim_metrics(self) -> Dict:
        """Collect metrics from UERANSIM simulation"""
        # In real implementation, this would query UERANSIM API
        # For now, return simulated data
        
        current_hour = datetime.now().hour
        
        # Simulate traffic patterns: high in evening, low at night
        if 18 <= current_hour <= 22:
            # Peak hours
            active_users = np.random.randint(400, 500)
            data_rate = np.random.uniform(30, 50)
            latency = np.random.uniform(15, 25)
        elif 1 <= current_hour <= 6:
            # Off-peak hours
            active_users = np.random.randint(50, 100)
            data_rate = np.random.uniform(1, 5)
            latency = np.random.uniform(5, 10)
        else:
            # Shoulder hours
            active_users = np.random.randint(150, 300)
            data_rate = np.random.uniform(10, 25)
            latency = np.random.uniform(10, 18)
        
        return {
            'active_users': active_users,
            'total_data_mbps': data_rate,
            'average_latency_ms': latency,
            'packet_loss_rate': np.random.uniform(0.0001, 0.001)
        }
    
    def collect_free5gc_metrics(self) -> Dict:
        """Collect metrics from free5GC core network"""
        # In real implementation, this would query free5GC API
        
        ueransim_data = self.collect_ueransim_metrics()
        
        # Simulate UPF throughput based on users
        throughput = ueransim_data['total_data_mbps'] * 0.95  # ~95% efficiency
        
        return {
            'throughput_mbps': throughput,
            'active_sessions': int(ueransim_data['active_users'] * 2.5),
            'amf_response_time_ms': np.random.uniform(10, 50),
            'smf_response_time_ms': np.random.uniform(5, 20)
        }
    
    def calculate_bs_metrics(self) -> tuple[Dict[int, float], Dict[int, float]]:
        """Calculate per-base-station metrics"""
        ueransim_data = self.collect_ueransim_metrics()
        
        # Distribute load across base stations
        bs_loads = {}
        bs_energy = {}
        
        total_users = ueransim_data['active_users']
        
        for bs_id in range(1, self.num_base_stations + 1):
            # Random load distribution
            users_per_bs = np.random.randint(0, max(1, total_users // self.num_base_stations))
            load_percentage = min(1.0, users_per_bs / 100.0)  # Assume 100 user capacity
            
            bs_loads[bs_id] = load_percentage * 100  # Convert to percentage
            
            # Energy calculation based on load
            # Idle: 500W, Active: 2000W, Sleep: 50W
            if load_percentage < 0.1:
                bs_energy[bs_id] = 50  # Sleep mode
            elif load_percentage < 0.2:
                bs_energy[bs_id] = 500 + (load_percentage / 0.2) * 1500
            else:
                bs_energy[bs_id] = 500 + load_percentage * 1500
        
        return bs_loads, bs_energy
    
    def collect_metrics(self) -> TrafficMetric:
        """Collect all metrics and return TrafficMetric object"""
        ueransim_data = self.collect_ueransim_metrics()
        free5gc_data = self.collect_free5gc_metrics()
        bs_loads, bs_energy = self.calculate_bs_metrics()
        
        total_energy = sum(bs_energy.values())
        active_bs = sum(1 for energy in bs_energy.values() if energy > 50)  # Active if > sleep power
        
        metric = TrafficMetric(
            timestamp=datetime.now(),
            active_users=ueransim_data['active_users'],
            total_data_mbps=ueransim_data['total_data_mbps'],
            average_latency_ms=ueransim_data['average_latency_ms'],
            throughput_mbps=free5gc_data['throughput_mbps'],
            packet_loss_rate=ueransim_data['packet_loss_rate'],
            energy_consumption_w=total_energy,
            active_base_stations=active_bs,
            bs_loads=bs_loads,
            bs_energy=bs_energy
        )
        
        self.metrics_history.append(metric)
        return metric
    
    def get_recent_metrics(self, duration_minutes: int = 60) -> pd.DataFrame:
        """Get metrics from the last N minutes as DataFrame"""
        cutoff_time = datetime.now() - timedelta(minutes=duration_minutes)
        recent = [m for m in self.metrics_history if m.timestamp >= cutoff_time]
        
        if not recent:
            return pd.DataFrame()
        
        data = {
            'timestamp': [m.timestamp for m in recent],
            'active_users': [m.active_users for m in recent],
            'data_mbps': [m.total_data_mbps for m in recent],
            'latency_ms': [m.average_latency_ms for m in recent],
            'throughput_mbps': [m.throughput_mbps for m in recent],
            'pkt_loss_rate': [m.packet_loss_rate for m in recent],
            'energy_w': [m.energy_consumption_w for m in recent],
            'active_bs': [m.active_base_stations for m in recent]
        }
        
        return pd.DataFrame(data)
    
    def get_average_metrics(self, duration_minutes: int = 60) -> Dict:
        """Calculate average metrics over a period"""
        df = self.get_recent_metrics(duration_minutes)
        
        if df.empty:
            return {}
        
        return {
            'avg_users': df['active_users'].mean(),
            'avg_data_mbps': df['data_mbps'].mean(),
            'avg_latency_ms': df['latency_ms'].mean(),
            'avg_throughput_mbps': df['throughput_mbps'].mean(),
            'avg_energy_w': df['energy_w'].mean(),
            'peak_users': df['active_users'].max(),
            'peak_energy_w': df['energy_w'].max()
        }
    
    def print_summary(self):
        """Print current traffic summary"""
        if not self.metrics_history:
            print("No metrics collected yet")
            return
        
        latest = self.metrics_history[-1]
        avg = self.get_average_metrics(60)
        
        print("\n" + "="*60)
        print("TRAFFIC MONITORING SUMMARY")
        print("="*60)
        print(f"Timestamp: {latest.timestamp}")
        print(f"\nCurrent Metrics:")
        print(f"  Active Users: {latest.active_users}")
        print(f"  Data Rate: {latest.total_data_mbps:.2f} Mbps")
        print(f"  Latency: {latest.average_latency_ms:.2f} ms")
        print(f"  Throughput: {latest.throughput_mbps:.2f} Mbps")
        print(f"  Energy: {latest.energy_consumption_w:.2f} W")
        print(f"  Active BS: {latest.active_base_stations}/{self.num_base_stations}")
        
        print(f"\n60-Minute Averages:")
        print(f"  Avg Users: {avg['avg_users']:.0f}")
        print(f"  Avg Energy: {avg['avg_energy_w']:.2f} W")
        print(f"  Peak Energy: {avg['peak_energy_w']:.2f} W")
        print("="*60 + "\n")


if __name__ == "__main__":
    monitor = TrafficMonitor()
    
    # Simulate 10 collections
    for i in range(10):
        metric = monitor.collect_metrics()
        print(f"Collection {i+1}: {metric.active_users} users, {metric.energy_consumption_w:.0f}W")
    
    monitor.print_summary()
