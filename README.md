# AI-Based Energy Efficient 5G using free5GC + UERANSIM

An intelligent system for optimizing energy consumption in 5G networks by predicting traffic patterns and dynamically controlling base station power states.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      UERANSIM (Simulation)                   │
│  ├─ Users (UE) Simulation                                    │
│  └─ Base Station (gNB) Simulation                            │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                  Traffic Monitoring                          │
│  ├─ Number of Active Users                                  │
│  ├─ Data Usage per User                                     │
│  ├─ Time-based Load Analysis                                │
│  └─ Latency & Throughput Metrics                            │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                   free5GC Core (Control Plane)              │
│  ├─ AMF (Authentication)                                    │
│  ├─ SMF (Session Management)                                │
│  └─ UPF (Data Routing)                                      │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                  AI Traffic Prediction                      │
│  ├─ LSTM/Time Series Models                                 │
│  ├─ Pattern Recognition                                     │
│  └─ Load Forecasting                                        │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│               Decision Engine (Smart Logic)                  │
│  ├─ Threshold-based Decisions                               │
│  ├─ Energy vs QoS Trade-offs                               │
│  └─ Optimization Algorithms                                 │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│            Base Station Control System                       │
│  ├─ ON/OFF Switching Logic                                  │
│  ├─ Load Balancing                                          │
│  └─ Dynamic State Management                                │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│                  Evaluation & Analytics                      │
│  ├─ Energy Consumption Analysis                             │
│  ├─ Latency Impact Measurement                              │
│  ├─ Performance Comparison (Normal vs AI-Optimized)         │
│  └─ Visualization & Reporting                               │
└─────────────────────────────────────────────────────────────┘
```

## Project Structure

```
AI 5g project/
├── src/
│   ├── ueransim_integration/      # UERANSIM integration & control
│   │   ├── ueransim_controller.py
│   │   └── ue_simulator.py
│   ├── free5gc_integration/       # free5GC integration & API
│   │   ├── free5gc_controller.py
│   │   └── metrics_collector.py
│   ├── traffic_monitoring/        # Real-time traffic monitoring
│   │   ├── traffic_monitor.py
│   │   ├── data_aggregator.py
│   │   └── metrics.py
│   ├── ai_model/                  # AI/ML components
│   │   ├── traffic_predictor.py
│   │   ├── lstm_model.py
│   │   └── feature_engineering.py
│   ├── decision_engine/           # Decision making logic
│   │   ├── decision_engine.py
│   │   ├── optimization.py
│   │   └── rules.py
│   └── base_station_control/      # BS control & state management
│       ├── bs_controller.py
│       ├── load_balancer.py
│       └── power_manager.py
├── evaluation/
│   ├── performance_analyzer.py    # Compare AI vs Normal
│   ├── metrics_calculator.py      # Energy, latency calculations
│   └── results_generator.py       # Generate reports
├── notebooks/                     # Jupyter notebooks for analysis
│   ├── traffic_analysis.ipynb
│   ├── model_training.ipynb
│   └── results_visualization.ipynb
├── scripts/
│   ├── run_simulation.py          # Main entry point
│   ├── setup_environment.sh       # Setup script
│   └── visualize_results.py       # Generate graphs
├── config/
│   ├── simulation_config.yaml     # Simulation parameters
│   ├── model_config.yaml          # AI model config
│   └── network_config.yaml        # Network topology
├── data/
│   ├── traffic_traces/            # Input traffic data
│   ├── model_weights/             # Trained model weights
│   └── results/                   # Output results & logs
├── requirements.txt               # Python dependencies
├── .gitignore
└── README.md                      # This file
```

## Key Components

### 1. Traffic Monitoring
- Collects real-time metrics from UERANSIM and free5GC
- Tracks: user count, data usage, latency, throughput
- Time-based load analysis (hourly, daily patterns)

### 2. AI Traffic Prediction
- LSTM-based time series models
- Predicts future load 1-24 hours ahead
- Learns patterns: low traffic (night), high traffic (evening)

### 3. Decision Engine
- Analyzes predicted traffic
- Makes binary decisions: Active or Sleep mode
- Optimizes energy consumption vs QoS

### 4. Base Station Control
- Dynamically switches base stations ON/OFF
- Load balancing across active stations
- Power state management

### 5. Evaluation
- Compares normal network vs AI-optimized system
- Graphs:
  - **Energy vs Time**: Shows power consumption reduction
  - **Latency vs Load**: Impacts of BS switching
  - **Active vs Sleep Duration**: Shows downtime periods

## Installation & Setup

### Prerequisites
- Python 3.8+
- UERANSIM (cloned separately)
- free5GC (cloned separately)
- Docker (for containerized free5GC)

### Setup Steps

1. **Clone this repository**
   ```bash
   cd "AI 5g project"
   ```

2. **Create Python virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure parameters**
   - Edit `config/simulation_config.yaml` for simulation settings
   - Edit `config/network_config.yaml` for network topology

5. **Setup UERANSIM & free5GC**
   Follow official documentation to build and run both systems

## Running the Project

### 1. Start the Network Simulation
```bash
python scripts/run_simulation.py --config config/simulation_config.yaml
```

### 2. Monitor Traffic in Real-time
```bash
python src/traffic_monitoring/traffic_monitor.py
```

### 3. Train AI Models
```bash
jupyter notebook notebooks/model_training.ipynb
```

### 4. Run Decision Engine & BS Control
```bash
python scripts/run_decision_engine.py
```

### 5. Generate Evaluation Results
```bash
python scripts/visualize_results.py
```

## Configuration Files

### simulation_config.yaml
```yaml
simulation:
  duration: 86400          # 24 hours in seconds
  num_users_min: 50
  num_users_max: 500
  num_base_stations: 10
  data_generation_pattern: "realistic"

traffic:
  peak_hours: [18, 19, 20, 21, 22]
  off_peak_hours: [1, 2, 3, 4, 5, 6]
```

### model_config.yaml
```yaml
ai_model:
  type: "lstm"
  lookback_window: 24           # Hours
  prediction_horizon: 24        # Hours
  lstm_units: 64
  epochs: 100
  batch_size: 32
```

## Performance Graphs

### 1. Energy vs Time
- X-axis: Time (hours)
- Y-axis: Power consumption (Watts)
- Two lines: Normal system vs AI-optimized
- Expected: AI system ~ 30-50% reduction

### 2. Latency vs Load
- X-axis: Number of active users
- Y-axis: Latency (milliseconds)
- Shows impact of BS switching on network performance

### 3. Active vs Sleep Duration
- X-axis: Time (hours)
- Y-axis: Number of active base stations
- Shows sleep periods when traffic is low

## Expected Results

| Metric | Normal System | AI-Optimized |
|--------|---------------|--------------|
| Energy Consumption | Baseline (100%) | -30 to -50% |
| Average Latency | - | ±5% (acceptable) |
| Peak Latency | - | Similar |
| BS Sleep Time | 0% | 30-50% |

## References

- [UERANSIM GitHub](https://github.com/aligungr/UERANSIM)
- [free5GC Documentation](https://free5gc.org/)
- [Time Series Forecasting with LSTM](https://www.tensorflow.org/tutorials/structured_data/time_series)
- [5G Energy Efficiency Studies](https://arxiv.org/)

## Contributors
- AI & ML: [Your Name]
- System Integration: [Your Name]
- Evaluation: [Your Name]

## License
MIT License

---

**Last Updated**: April 2026
**Status**: Project Setup Complete
