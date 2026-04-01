"""
Decision Engine
Smart logic for base station on/off decisions based on traffic predictions
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class Decision:
    """Decision output for base stations"""
    timestamp: str
    bs_commands: Dict[int, str]  # BS_ID -> "ON" or "SLEEP"
    reasons: Dict[int, str]       # Explanation for each BS
    energy_saving_percentage: float
    expected_latency_impact_ms: float
    confidence_score: float


class DecisionEngine:
    """
    Decision engine for controlling base stations
    Makes ON/OFF decisions based on traffic predictions and rules
    """
    
    def __init__(self, 
                 num_bs: int = 10,
                 sleep_threshold: float = 0.2,
                 active_threshold: float = 0.5,
                 hysteresis_margin: float = 0.05):
        """
        Initialize decision engine
        
        Args:
            num_bs: Number of base stations
            sleep_threshold: Load % below which BS goes to sleep
            active_threshold: Load % above which BS must be active
            hysteresis_margin: Margin to prevent oscillation
        """
        self.num_bs = num_bs
        self.sleep_threshold = sleep_threshold
        self.active_threshold = active_threshold
        self.hysteresis_margin = hysteresis_margin
        
        # Track BS states
        self.bs_states = {bs_id: "ON" for bs_id in range(1, num_bs + 1)}
        self.state_history = []
        
    def make_decision(self,
                     traffic_prediction: Dict,
                     current_loads: Dict[int, float],
                     bs_energy: Dict[int, float]) -> Decision:
        """
        Make ON/OFF decisions for all base stations
        
        Args:
            traffic_prediction: AI model prediction (peak_load, average_load, predictions list)
            current_loads: Current load % for each BS {BS_ID -> Load %}
            bs_energy: Current energy consumption for each BS {BS_ID -> Power W}
        
        Returns:
            Decision object with commands for each BS
        """
        from datetime import datetime
        
        bs_commands = {}
        reasons = {}
        
        predicted_peak = traffic_prediction.get('peak_load', 100)
        predicted_avg = traffic_prediction.get('average_load', 50)
        
        # Calculate required active BSs based on prediction
        required_active_bs = self._calculate_required_bs(predicted_peak)
        
        # Sort BSs by current load (highest first)
        sorted_bs = sorted(current_loads.items(), key=lambda x: x[1], reverse=True)
        
        active_count = 0
        
        for bs_id, load in sorted_bs:
            current_state = self.bs_states[bs_id]
            decision = None
            reason = ""
            
            # Rule 1: Must-stay-active threshold
            if load > self.active_threshold:
                decision = "ON"
                reason = f"Load {load:.1f}% > active threshold {self.active_threshold*100:.0f}%"
                active_count += 1
            
            # Rule 2: Must-sleep threshold with hysteresis
            elif load < self.sleep_threshold:
                if current_state == "ON":
                    # Only switch if below sleep threshold - hysteresis
                    if load < self.sleep_threshold - self.hysteresis_margin:
                        decision = "SLEEP"
                        reason = f"Load {load:.1f}% < sleep threshold {self.sleep_threshold*100:.0f}%"
                    else:
                        decision = "ON"
                        reason = f"Hysteresis: keeping ON (load {load:.1f}%)"
                        active_count += 1
                else:
                    decision = "SLEEP"
                    reason = f"Load {load:.1f}% < sleep threshold"
            
            # Rule 3: Gray zone - use optimization
            else:
                if active_count < required_active_bs:
                    decision = "ON"
                    reason = f"Optimization: required active BS count"
                    active_count += 1
                else:
                    decision = "SLEEP"
                    reason = f"Optimization: sufficient coverage from other BS"
            
            bs_commands[bs_id] = decision
            reasons[bs_id] = reason
            self.bs_states[bs_id] = decision
        
        # Calculate metrics
        energy_saving = self._calculate_energy_saving(bs_energy, bs_commands)
        latency_impact = self._estimate_latency_impact(
            current_loads, bs_commands, required_active_bs, active_count
        )
        
        decision = Decision(
            timestamp=datetime.now().isoformat(),
            bs_commands=bs_commands,
            reasons=reasons,
            energy_saving_percentage=energy_saving,
            expected_latency_impact_ms=latency_impact,
            confidence_score=self._calculate_confidence(traffic_prediction)
        )
        
        self.state_history.append(decision)
        return decision
    
    def _calculate_required_bs(self, peak_load: float) -> int:
        """
        Calculate number of BS needed for peak load
        Assume each BS can handle 100 users
        """
        users_per_bs = 100
        required = max(2, int(np.ceil(peak_load / users_per_bs)))  # At least 2 for redundancy
        return min(self.num_bs, required)
    
    def _calculate_energy_saving(self, bs_energy: Dict[int, float], 
                                 bs_commands: Dict[int, str]) -> float:
        """Calculate expected energy saving percentage"""
        baseline_energy = sum(bs_energy.values())
        
        if baseline_energy == 0:
            return 0
        
        # Simulate energy if decisions are applied
        optimized_energy = 0
        for bs_id, command in bs_commands.items():
            if command == "SLEEP":
                optimized_energy += 50  # Sleep power
            else:
                optimized_energy += bs_energy[bs_id]
        
        saving = (baseline_energy - optimized_energy) / baseline_energy * 100
        return max(0, saving)
    
    def _estimate_latency_impact(self, current_loads: Dict[int, float],
                                bs_commands: Dict[int, str],
                                required_bs: int,
                                active_bs: int) -> float:
        """
        Estimate latency increase from BS switching
        
        More BS sleeping = higher load on active BS = higher latency
        """
        if active_bs == 0:
            return 100  # Critical: no BS active
        
        # Load imbalance increases latency
        avg_new_load = sum(current_loads.values()) / active_bs if active_bs > 0 else 0
        
        # Latency increases ~exponentially with load > 80%
        if avg_new_load > 0.8:
            latency_impact = (avg_new_load - 0.8) * 20  # Up to 4ms at 100% load
        else:
            latency_impact = 0
        
        # Penalty if BSs are sleeping
        sleep_penalty = (self.num_bs - active_bs) * 0.1
        
        return latency_impact + sleep_penalty
    
    def _calculate_confidence(self, traffic_prediction: Dict) -> float:
        """
        Calculate confidence in decision
        Lower confidence for unexpected traffic patterns
        """
        # Use prediction confidence if available
        if 'confidence' in traffic_prediction:
            return traffic_prediction['confidence']
        
        # Default confidence based on historical accuracy
        return 0.85


class OptimizationEngine:
    """
    Advanced optimization using different strategies
    """
    
    @staticmethod
    def minimize_energy(current_loads: Dict[int, float],
                       bs_energy: Dict[int, float],
                       required_active_bs: int) -> Dict[int, str]:
        """
        Greedy algorithm: minimize energy consumption
        Turn off BS with lowest load first
        """
        commands = {}
        
        # Sort by load (ascending)
        sorted_bs = sorted(current_loads.items(), key=lambda x: x[1])
        
        active_count = 0
        for bs_id, load in sorted_bs:
            if active_count < required_active_bs:
                commands[bs_id] = "ON"
                active_count += 1
            else:
                commands[bs_id] = "SLEEP"
        
        return commands
    
    @staticmethod
    def balance_load(current_loads: Dict[int, float],
                    required_active_bs: int) -> Dict[int, str]:
        """
        Load balancing: keep highest-load BSs active
        Minimum load imbalance
        """
        commands = {}
        
        # Sort by load (descending)
        sorted_bs = sorted(current_loads.items(), key=lambda x: x[1], reverse=True)
        
        for idx, (bs_id, load) in enumerate(sorted_bs):
            if idx < required_active_bs:
                commands[bs_id] = "ON"
            else:
                commands[bs_id] = "SLEEP"
        
        return commands
    
    @staticmethod
    def maximize_qos(current_loads: Dict[int, float],
                    bs_quality: Dict[int, float],
                    required_active_bs: int) -> Dict[int, str]:
        """
        Quality-aware: keep high-quality BSs active
        """
        commands = {}
        
        # Sort by quality metric (descending)
        sorted_bs = sorted(zip(current_loads.keys(),
                              [bs_quality.get(bs_id, 0.5) for bs_id in current_loads.keys()]),
                          key=lambda x: x[1], reverse=True)
        
        for idx, (bs_id, _) in enumerate(sorted_bs):
            if idx < required_active_bs:
                commands[bs_id] = "ON"
            else:
                commands[bs_id] = "SLEEP"
        
        return commands


if __name__ == "__main__":
    # Example usage
    engine = DecisionEngine(num_bs=10)
    
    mock_prediction = {
        'peak_load': 150,
        'average_load': 75,
        'confidence': 0.9
    }
    
    mock_loads = {i: np.random.uniform(10, 80) for i in range(1, 11)}
    mock_energy = {i: 500 + mock_loads[i] * 15 for i in range(1, 11)}
    
    decision = engine.make_decision(mock_prediction, mock_loads, mock_energy)
    
    print("Decision Engine Output:")
    print(f"Timestamp: {decision.timestamp}")
    print(f"Energy Saving: {decision.energy_saving_percentage:.1f}%")
    print(f"Latency Impact: {decision.expected_latency_impact_ms:.2f} ms")
    print(f"\nBase Station Commands:")
    for bs_id in sorted(decision.bs_commands.keys()):
        print(f"  BS {bs_id}: {decision.bs_commands[bs_id]} ({decision.reasons[bs_id]})")
