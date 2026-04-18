"""
Base Station Control System
Manages dynamic switching and power states of base stations
"""

import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging
import sys
from pathlib import Path

# Add src to path for imports
if str(Path(__file__).parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from ueransim_integration.ueransim_controller import UERANSIMController
except ImportError:
    UERANSIMController = None

logger = logging.getLogger(__name__)


@dataclass
class BaseStationState:
    """Current state of a base station"""
    bs_id: int
    state: str  # "ON", "SLEEP", "TRANSITIONING"
    power_consumption_w: float
    current_load_percentage: float
    users_connected: int
    transition_start_time: Optional[datetime] = None
    transition_duration_sec: int = 0


class BaseStationController:
    """
    Controls base station power states and transitions
    Handles ON->SLEEP and SLEEP->ON transitions with time delays
    """
    
    def __init__(self, num_bs: int = 10):
        """Initialize controller for N base stations"""
        self.num_bs = num_bs
        self.bs_states: Dict[int, BaseStationState] = {}
        self.transition_log: List[Dict] = []
        self.ueransim = UERANSIMController() if UERANSIMController else None
        
        # Power consumption models (Watts)
        self.power_model = {
            'idle': 500,
            'active': 2000,
            'sleep': 50,
            'sleep_to_active_time': 30,  # seconds
            'active_to_sleep_time': 10   # seconds
        }
        
        # Initialize all BS as ON
        for bs_id in range(1, num_bs + 1):
            self.bs_states[bs_id] = BaseStationState(
                bs_id=bs_id,
                state="ON",
                power_consumption_w=500,
                current_load_percentage=0,
                users_connected=0
            )
    
    def apply_decision(self, 
                      bs_commands: Dict[int, str],
                      current_loads: Dict[int, float],
                      current_users: Dict[int, int],
                      timestamp: datetime = None) -> Dict[int, BaseStationState]:
        """
        Apply decision engine commands to base stations
        
        Args:
            bs_commands: {BS_ID -> "ON" or "SLEEP"}
            current_loads: {BS_ID -> Load %}
            current_users: {BS_ID -> User count}
            timestamp: Current simulation timestamp
        
        Returns:
            Updated base station states
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        for bs_id, command in bs_commands.items():
            current_state = self.bs_states[bs_id].state
            
            # Handle transitions
            if current_state == "ON" and command == "SLEEP":
                self._start_transition(bs_id, "ON", "SLEEP", timestamp)
            
            elif current_state == "SLEEP" and command == "ON":
                self._start_transition(bs_id, "SLEEP", "ON", timestamp)
            
            # Update load and users
            self.bs_states[bs_id].current_load_percentage = current_loads.get(bs_id, 0)
            self.bs_states[bs_id].users_connected = current_users.get(bs_id, 0)
    
    def update_transitions(self, current_time: datetime = None) -> Dict[int, bool]:
        """
        Update transitioning base stations
        Check if transition is complete
        
        Returns:
            Dict[BS_ID -> transition_complete]
        """
        if current_time is None:
            current_time = datetime.now()
        
        transition_complete = {}
        
        for bs_id, state in self.bs_states.items():
            if state.state == "TRANSITIONING":
                elapsed = (current_time - state.transition_start_time).total_seconds()
                
                if elapsed >= state.transition_duration_sec:
                    # Transition complete
                    state.state = getattr(self, f'_transition_target_{bs_id}', "ON")
                    state.transition_start_time = None
                    transition_complete[bs_id] = True
                    logger.info(f"BS {bs_id} transition complete")
                else:
                    transition_complete[bs_id] = False
            else:
                transition_complete[bs_id] = True
        
        return transition_complete
    
    def _start_transition(self, bs_id: int, from_state: str, to_state: str, 
                         timestamp: datetime):
        """
        Start state transition with delay
        """
        self.bs_states[bs_id].state = "TRANSITIONING"
        self.bs_states[bs_id].transition_start_time = timestamp
        
        if from_state == "ON" and to_state == "SLEEP":
            self.bs_states[bs_id].transition_duration_sec = self.power_model['active_to_sleep_time']
            target = "SLEEP"
        else:
            self.bs_states[bs_id].transition_duration_sec = self.power_model['sleep_to_active_time']
            target = "ON"
        
        # Store target state internally
        setattr(self, f'_transition_target_{bs_id}', target)
        
        # Trigger Linux integration if applicable
        if self.ueransim:
            if target == "SLEEP":
                self.ueransim.stop_gnb(bs_id)
            elif target == "ON":
                config_file = f"free5gc-gnb-{bs_id}.yaml"
                self.ueransim.start_gnb(bs_id, config_file)
        
        self.transition_log.append({
            'timestamp': timestamp,
            'bs_id': bs_id,
            'from_state': from_state,
            'to_state': to_state,
            'duration_sec': self.bs_states[bs_id].transition_duration_sec
        })
        
        logger.info(f"BS {bs_id}: Starting transition {from_state} -> {to_state}")
    
    def calculate_power(self, bs_id: int) -> float:
        """
        Calculate power consumption for a BS based on state
        """
        state = self.bs_states[bs_id]
        
        if state.state == "SLEEP":
            return self.power_model['sleep']
        
        elif state.state == "TRANSITIONING":
            # Linear interpolation during transition
            elapsed = (datetime.now() - state.transition_start_time).total_seconds()
            progress = min(1.0, elapsed / state.transition_duration_sec)
            
            if 'Sleep' in getattr(self, f'_transition_target_{bs_id}', 'ON'):
                # On -> Sleep: decrease from active to sleep
                return self.power_model['active'] - (
                    self.power_model['active'] - self.power_model['sleep']
                ) * progress
            else:
                # Sleep -> On: increase from sleep to active
                return self.power_model['sleep'] + (
                    self.power_model['active'] - self.power_model['sleep']
                ) * progress
        
        else:  # ON state
            # Power scales with load
            load = state.current_load_percentage / 100.0
            return self.power_model['idle'] + load * (self.power_model['active'] - self.power_model['idle'])
    
    def get_total_power(self) -> float:
        """Get total network power consumption"""
        total = 0
        for bs_id in range(1, self.num_bs + 1):
            self.bs_states[bs_id].power_consumption_w = self.calculate_power(bs_id)
            total += self.bs_states[bs_id].power_consumption_w
        
        return total
    
    def get_active_bs_count(self) -> int:
        """Count number of active base stations"""
        return sum(1 for state in self.bs_states.values() 
                  if state.state == "ON")
    
    def get_sleeping_bs_count(self) -> int:
        """Count number of sleeping base stations"""
        return sum(1 for state in self.bs_states.values() 
                  if state.state == "SLEEP")
    
    def get_transitioning_bs_count(self) -> int:
        """Count number of transitioning base stations"""
        return sum(1 for state in self.bs_states.values() 
                  if state.state == "TRANSITIONING")
    
    def get_status_summary(self) -> Dict:
        """Get summary of all base stations"""
        total_power = self.get_total_power()
        
        summary = {
            'timestamp': datetime.now().isoformat(),
            'total_power_w': total_power,
            'active_bs': self.get_active_bs_count(),
            'sleeping_bs': self.get_sleeping_bs_count(),
            'transitioning_bs': self.get_transitioning_bs_count(),
            'bs_details': {}
        }
        
        for bs_id in range(1, self.num_bs + 1):
            state = self.bs_states[bs_id]
            summary['bs_details'][bs_id] = {
                'state': state.state,
                'power_w': state.power_consumption_w,
                'load_percent': state.current_load_percentage,
                'users': state.users_connected
            }
        
        return summary
    
    def print_status(self):
        """Print current status of all base stations"""
        summary = self.get_status_summary()
        
        print("\n" + "="*70)
        print("BASE STATION CONTROL STATUS")
        print("="*70)
        print(f"Timestamp: {summary['timestamp']}")
        print(f"Total Network Power: {summary['total_power_w']:.0f}W")
        print(f"Active BS: {summary['active_bs']} | Sleeping: {summary['sleeping_bs']} | Transitioning: {summary['transitioning_bs']}")
        print("\n{:<6} {:<12} {:<10} {:<10} {:<10}".format("BS_ID", "STATE", "POWER(W)", "LOAD(%)", "USERS"))
        print("-"*70)
        
        for bs_id in range(1, self.num_bs + 1):
            details = summary['bs_details'][bs_id]
            print("{:<6} {:<12} {:<10.0f} {:<10.1f} {:<10}".format(
                bs_id,
                details['state'],
                details['power_w'],
                details['load_percent'],
                details['users']
            ))
        
        print("="*70 + "\n")


class LoadBalancer:
    """
    Balances loads across active base stations
    Redistributes users when BSs transition states
    """
    
    @staticmethod
    def redistribute_load(current_loads: Dict[int, float],
                         bs_commands: Dict[int, str],
                         traffic_increase_factor: float = 1.5) -> Dict[int, float]:
        """
        Redistribute load when base stations change states
        
        Sleeping BSs' load redistributed to active BSs
        This increases load on active BSs
        
        Args:
            current_loads: Current load on each BS
            bs_commands: Decision commands (ON/SLEEP)
            traffic_increase_factor: Load increase factor when BS sleeps (~50%)
        
        Returns:
            Updated loads after redistribution
        """
        new_loads = current_loads.copy()
        total_sleeping_load = 0
        active_bs = []
        
        # Identify sleeping BSs and their load
        for bs_id, command in bs_commands.items():
            if command == "SLEEP":
                total_sleeping_load += current_loads.get(bs_id, 0)
                new_loads[bs_id] = 0.001  # Minimal load when sleeping
            else:
                active_bs.append(bs_id)
        
        # Redistribute sleeping load among active BSs
        if active_bs:
            per_bs_additional = (total_sleeping_load * traffic_increase_factor) / len(active_bs)
            for bs_id in active_bs:
                new_loads[bs_id] += per_bs_additional
                new_loads[bs_id] = min(100, new_loads[bs_id])  # Cap at 100%
        
        return new_loads
    
    @staticmethod
    def get_handover_cost(original_load: float, new_load: float) -> float:
        """
        Calculate handover cost (latency penalty)
        Larger load increase = higher handover drops
        
        Returns:
            Estimated latency increase in milliseconds
        """
        load_increase = new_load - original_load
        if load_increase <= 0:
            return 0
        
        # Handover cost: ~0.1ms per 1% load increase
        return load_increase * 0.1


if __name__ == "__main__":
    # Example usage
    controller = BaseStationController(num_bs=10)
    
    # Simulate decision
    mock_commands = {
        1: "ON", 2: "ON", 3: "ON", 4: "ON", 5: "ON",
        6: "SLEEP", 7: "SLEEP", 8: "SLEEP", 9: "SLEEP", 10: "SLEEP"
    }
    
    mock_loads = {i: np.random.uniform(20, 80) for i in range(1, 11)}
    mock_users = {i: int(np.random.uniform(10, 80)) for i in range(1, 11)}
    
    controller.apply_decision(mock_commands, mock_loads, mock_users)
    controller.print_status()
