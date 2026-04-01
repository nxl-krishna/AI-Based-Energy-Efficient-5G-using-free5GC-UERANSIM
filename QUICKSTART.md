# Quick Start Guide for AI-Based Energy Efficient 5G

## 1. Prerequisites

- Python 3.8+
- pip or conda
- UERANSIM (optional, for real integration)
- free5GC (optional, for real integration)

## 2. Installation

### Option A: Bash/Linux/Mac
```bash
bash setup_environment.sh
```

### Option B: Windows (PowerShell)
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
mkdir -p data\traffic_logs, data\model_weights, data\results, data\logs
```

### Option C: Manual Setup
```bash
# Create virtual environment
python -m venv venv

# Activate it
source venv/bin/activate  # Linux/Mac
# OR
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

## 3. Configuration

Edit the configuration files before running:

```bash
# Edit simulation parameters
nano config/simulation_config.yaml

# Edit network topology
nano config/network_config.yaml
```

Key parameters:
- `duration`: Simulation duration in seconds (default: 86400 = 24 hours)
- `num_base_stations`: Number of base stations (default: 10)
- `num_users_min/max`: User count range
- `sleep_threshold`: Load below which BS goes to sleep (default: 0.2 = 20%)
- `active_threshold`: Load above which BS must be active (default: 0.5 = 50%)

## 4. Running the Simulation

### Basic Run
```bash
cd scripts
python run_simulation.py
```

### With Configuration
```bash
python run_simulation.py --config ../config/simulation_config.yaml
```

### Monitor Progress
The simulator will print progress every 10% completion.

## 5. Analyzing Results

Results are saved to `data/results/`:

```bash
cd evaluation
python performance_analyzer.py
```

This generates:
- `energy_vs_time.png` - Power consumption comparison
- `latency_vs_load.png` - Latency impact analysis
- `bs_states.png` - Base station activity timeline
- `evaluation_report.txt` - Detailed summary

## 6. Using Jupyter Notebooks

```bash
jupyter notebook notebooks/
```

Available notebooks:
- `traffic_analysis.ipynb` - Explore traffic patterns
- `model_training.ipynb` - Train LSTM models
- `results_visualization.ipynb` - Visualize results

## 7. Integration with UERANSIM & free5GC

### For Real Integration:

1. **Setup UERANSIM**
   ```bash
   git clone https://github.com/aligungr/UERANSIM.git
   cd UERANSIM
   mkdir build && cd build
   cmake ..
   make -j$(nproc)
   ```

2. **Setup free5GC**
   ```bash
   git clone https://github.com/free5gc/free5gc.git
   cd free5gc
   go mod download
   ```

3. **Update integration scripts**
   - Edit `src/ueransim_integration/ueransim_controller.py`
   - Update API endpoints to match your setup
   - Configure UERANSIM command-line options

4. **Run with real integration**
   ```bash
   # Terminal 1: Start free5GC
   cd free5gc
   ./run.sh
   
   # Terminal 2: Start UERANSIM
   cd UERANSIM/build
   ./nr-ue -c config.yaml
   
   # Terminal 3: Run AI system
   python scripts/run_simulation.py
   ```

## 8. Expected Results

With AI optimization, you should see:

| Metric | Expected Value |
|--------|-----------------|
| Energy Saving | 30-50% reduction |
| Average Latency Impact | < 5% increase |
| Base Station Utilization | 50-80% active |
| Peak Hour Load | Well-balanced |

## 9. Troubleshooting

### Python Import Errors
```bash
# Add src to Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"
```

### Missing TensorFlow
```bash
pip install tensorflow>=2.13.0
```

### Permission Denied (Linux/Mac)
```bash
chmod +x setup_environment.sh
chmod +x scripts/*.py
```

### No GPU Detected
```bash
# Use CPU only (slower but works)
# Edit training scripts to use CPU
```

## 10. Project Structure Understanding

```
src/
├── traffic_monitoring/    # Real-time metrics collection
├── ai_model/             # LSTM/prediction models
├── decision_engine/      # ON/OFF decision logic
└── base_station_control/ # Power state management

evaluation/
└── performance_analyzer.py # Results analysis

scripts/
├── run_simulation.py      # Main entry point
└── visualize_results.py   # Generate graphs

config/
├── simulation_config.yaml # Simulation parameters
└── network_config.yaml    # Network topology
```

## 11. Advanced Usage

### Custom Thresholds
```python
from src.decision_engine.decision_engine import DecisionEngine

engine = DecisionEngine(
    num_bs=10,
    sleep_threshold=0.15,      # More aggressive sleep
    active_threshold=0.6,      # Require higher load
    hysteresis_margin=0.1      # Prevent oscillation
)
```

### Custom ML Model
```python
from src.ai_model.traffic_predictor import TrafficPredictor

predictor = TrafficPredictor(
    lookback_window=48,        # Use 2 days of history
    prediction_horizon=48      # Predict 2 days ahead
)
```

### Load Balancing Strategies
```python
from src.base_station_control.bs_controller import LoadBalancer

# Different strategies available:
# - redistribute_load()    # General redistribution
# - minimize_energy()      # Energy optimization
# - balance_load()         # Load balance
# - maximize_qos()         # QoS optimization
```

## 12. Performance Optimization Tips

1. **Reduce simulation duration** for faster runs
   ```yaml
   duration: 3600  # 1 hour instead of 24
   ```

2. **Increase time step** for coarser granularity
   ```yaml
   time_step: 300  # 5 minutes instead of 1
   ```

3. **Use GPU** for faster training
   ```bash
   pip install tensorflow-gpu
   ```

4. **Parallel processing** for large simulations
   - Use multiprocessing for per-BS calculations

## 13. Contributing & Feedback

- Report issues on GitHub
- Submit pull requests for improvements
- Share evaluation results

---

**Last Updated**: April 2026
**Version**: 1.0
**Status**: Ready for Development
