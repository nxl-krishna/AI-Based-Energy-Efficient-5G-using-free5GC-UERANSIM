"""
Main Simulation Runner
Orchestrates the complete AI-based energy-efficient 5G system

Changes:
  - UERANSIMController now starts/stops gNB and UE Docker containers.
  - EnergyPredictor trains on real RAPL-measured energy after warm-up.
  - CSV output includes: UE, Throughput, CPU, Memory, Energy columns.
"""

import sys
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import logging
import yaml
from pathlib import Path

# Import custom modules
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from traffic_monitoring.traffic_monitor import TrafficMonitor
from ai_model.traffic_predictor import SimplePredictor, EnergyPredictor
from decision_engine.decision_engine import DecisionEngine
from base_station_control.bs_controller import BaseStationController, LoadBalancer
from ueransim_integration.ueransim_controller import UERANSIMController

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SimulationRunner:
    """
    Main simulation orchestrator.
    Integrates all components: monitoring, prediction, decision, control.
    Manages Docker-based UERANSIM gNB and UE containers.
    """

    def __init__(self, config_file: str = None, compose_dir: str = "."):
        """Initialize simulator with configuration.

        Args:
            config_file: Optional YAML config path.
            compose_dir: Directory containing docker-compose.yaml.
                         Set to the project root on your Linux host.
        """

        # Default configuration
        self.config = {
            'simulation': {
                'duration': 86400,  # 24 hours
                'time_step': 60,    # 1 minute
                'num_base_stations': 10
            },
            'ai_model': {
                'update_interval_sec': 3600  # Update predictions hourly
            },
            'decision': {
                'update_interval_sec': 300    # Make decisions every 5 min
            }
        }

        # Load config if provided
        if config_file and Path(config_file).exists():
            with open(config_file, 'r') as f:
                self.config.update(yaml.safe_load(f))

        # Initialize components
        num_bs = self.config['simulation'].get('num_base_stations', 10)
        self.monitor         = TrafficMonitor(num_bs=num_bs)
        self.predictor       = SimplePredictor(lookback_window=24)
        self.energy_pred     = EnergyPredictor()          # Real energy model
        self.decision_engine = DecisionEngine(num_bs=num_bs)
        self.controller      = BaseStationController(num_bs=num_bs)

        # Docker-based UERANSIM controller
        self.ueransim = UERANSIMController(compose_dir=compose_dir)

        # Tracking
        self.simulation_time = datetime.now()
        self.results = {
            'metrics':           [],
            'decisions':         [],
            'power_consumption': [],
            'bs_states':         []
        }

        logger.info("Simulation initialized")
    
    def run(self, duration_hours: int = 24, visualize: bool = True):
        """
        Run the simulation.

        Starts gNB and UE Docker containers before the loop and stops
        them cleanly on completion or error.

        Args:
            duration_hours: How many hours to simulate.
            visualize:      Whether to save results for visualization.
        """
        duration_sec = duration_hours * 3600
        time_step    = self.config['simulation'].get('time_step', 60)

        logger.info(f"Starting simulation: {duration_hours} hours")

        # --- Start Docker containers ---
        logger.info("Starting UERANSIM gNB container...")
        self.ueransim.start_gnb()
        logger.info("Starting UERANSIM UE container...")
        self.ueransim.start_ue()

        steps = duration_sec // time_step

        try:
            for step in range(steps):
                current_hour = (step * time_step) / 3600

                # Step 1: Collect traffic metrics
                metric = self.monitor.collect_metrics()
                self.results['metrics'].append(metric)

                # Step 2: Update traffic predictions (every hour)
                if step % (3600 // time_step) == 0:
                    self._update_predictions()

                # Step 3: Train energy model after 10 samples of warm-up
                if step == 10:
                    self._train_energy_predictor()

                # Step 4: Make decision every 5 minutes
                if step % (300 // time_step) == 0:
                    decision = self._make_decision(metric)
                    self.results['decisions'].append(decision)

                    # Step 5: Apply decision
                    self._apply_decision(decision, metric)

                # Step 6: Log results
                self._log_results()

                # Progress indicator
                if (step + 1) % max(1, (steps // 10)) == 0:
                    progress = ((step + 1) / steps) * 100
                    logger.info(f"Progress: {progress:.0f}% ({current_hour:.1f}h)")

        finally:
            # --- Always stop containers, even on error ---
            logger.info("Stopping UERANSIM containers...")
            self.ueransim.stop_ue()
            self.ueransim.stop_gnb()

        logger.info("Simulation completed")

        if visualize:
            self.save_results()
    
    def _update_predictions(self):
        """Update AI traffic predictions."""
        if len(self.results['metrics']) < 24:
            return

        # Get recent traffic data
        recent_metrics = self.results['metrics'][-24:]
        active_users   = np.array([m.active_users for m in recent_metrics])

        # Train or predict
        if not hasattr(self.predictor, 'hourly_patterns') or not self.predictor.hourly_patterns:
            data = pd.DataFrame({
                'timestamp':    [m.timestamp    for m in recent_metrics],
                'active_users': active_users
            })
            self.predictor.train(data)

        logger.info("Traffic predictions updated")

    def _train_energy_predictor(self):
        """Train the EnergyPredictor on collected RAPL-measured data."""
        df = self.monitor.get_recent_metrics(duration_minutes=60)
        if df.empty or len(df) < 5:
            logger.warning("Not enough data to train EnergyPredictor yet.")
            return
        try:
            metrics = self.energy_pred.train(df)
            logger.info(f"EnergyPredictor trained: {metrics}")
        except Exception as e:
            logger.warning(f"EnergyPredictor training skipped: {e}")
    
    def _make_decision(self, current_metric) -> dict:
        """Make ON/OFF decisions for base stations"""
        
        # Get prediction
        recent_data = np.array([m.active_users for m in self.results['metrics'][-24:]])
        if len(recent_data) < 24:
            recent_data = np.pad(recent_data, (24 - len(recent_data), 0))
        
        try:
            prediction = self.predictor.predict_next_hours(num_hours=24)
        except:
            prediction = {
                'peak_load': np.mean(recent_data) * 1.2,
                'average_load': np.mean(recent_data)
            }
        
        # Make decision
        decision = self.decision_engine.make_decision(
            traffic_prediction=prediction,
            current_loads=current_metric.bs_loads,
            bs_energy=current_metric.bs_energy
        )
        
        logger.info(f"Decision made: {sum(1 for c in decision.bs_commands.values() if c == 'ON')} BS active")
        
        return decision
    
    def _apply_decision(self, decision, metric):
        """Apply decision engine commands to base stations"""
        
        # Redistribute load due to sleeping BSs
        new_loads = LoadBalancer.redistribute_load(
            metric.bs_loads,
            decision.bs_commands
        )
        
        # Get user distribution
        user_dist = {bs_id: int(new_loads[bs_id] / 100 * 50) 
                    for bs_id in range(1, self.monitor.num_base_stations + 1)}
        
        # Apply to controller
        self.controller.apply_decision(
            decision.bs_commands,
            new_loads,
            user_dist,
            datetime.now()
        )
        
        # Update transitions
        self.controller.update_transitions()
    
    def _log_results(self):
        """Log current state to results"""
        power = self.controller.get_total_power()
        self.results['power_consumption'].append({
            'timestamp': datetime.now(),
            'total_power_w': power
        })
        
        summary = self.controller.get_status_summary()
        self.results['bs_states'].append(summary)
    
    def save_results(self, output_dir: str = None):
        """Save results to files for analysis."""
        if output_dir is None:
            output_dir = str(Path(__file__).parent.parent / 'data' / 'results')
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Save metrics in standardised CSV format: UE,Throughput,CPU,Memory,Energy
        df_metrics = self.monitor.get_recent_metrics(duration_minutes=99999)
        if df_metrics.empty:
            # Fallback if metrics_history empty after pipeline refactor
            df_metrics = pd.DataFrame({
                'timestamp':  [m.timestamp           for m in self.results['metrics']],
                'UE':         [m.active_users         for m in self.results['metrics']],
                'Throughput': [m.throughput_mbps      for m in self.results['metrics']],
                'CPU':        [m.cpu_percent          for m in self.results['metrics']],
                'Memory':     [m.memory_percent       for m in self.results['metrics']],
                'Energy':     [m.energy_consumption_w for m in self.results['metrics']],
            })
        df_metrics.to_csv(output_path / 'traffic_metrics.csv', index=False)
        logger.info(f"Metrics CSV saved: {output_path / 'traffic_metrics.csv'}")

        # Save power consumption log
        df_power = pd.DataFrame(self.results['power_consumption'])
        df_power.to_csv(output_path / 'power_consumption.csv', index=False)

        logger.info(f"Results saved to {output_path}")
    
    def print_summary(self):
        """Print simulation summary"""
        print("\n" + "="*70)
        print("SIMULATION SUMMARY")
        print("="*70)
        
        if self.results['metrics']:
            avg_users = np.mean([m.active_users for m in self.results['metrics']])
            avg_energy = np.mean([m.energy_consumption_w for m in self.results['metrics']])
            peak_energy = max([m.energy_consumption_w for m in self.results['metrics']])
            
            print(f"Average Active Users: {avg_users:.0f}")
            print(f"Average Network Power: {avg_energy:.0f}W")
            print(f"Peak Network Power: {peak_energy:.0f}W")
        
        print(f"\nTotal Metrics Collected: {len(self.results['metrics'])}")
        print(f"Total Decisions Made: {len(self.results['decisions'])}")
        
        print("="*70 + "\n")


def main():
    """Main entry point."""

    # compose_dir should point to where docker-compose.yaml lives on Linux.
    # On your Linux host: set COMPOSE_PROJECT_DIR env var, or edit this path.
    import os
    compose_dir = os.environ.get("COMPOSE_PROJECT_DIR", ".")

    simulator = SimulationRunner(
        config_file='../../config/simulation_config.yaml',
        compose_dir=compose_dir,
    )

    try:
        simulator.run(duration_hours=24)
        simulator.print_summary()
    except Exception as e:
        logger.error(f"Simulation error: {e}")
        raise


if __name__ == "__main__":
    main()
