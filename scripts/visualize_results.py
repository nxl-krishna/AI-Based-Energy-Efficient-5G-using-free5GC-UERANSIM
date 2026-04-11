import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
import time
import os

# Set page config
st.set_page_config(
    page_title="AI 5G Energy Optimizer",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for premium design
st.markdown("""
<style>
    .main {
        background-color: #0e1117;
    }
    h1, h2, h3 {
        color: #00d2ff;
        font-family: 'Inter', sans-serif;
        font-weight: 600;
    }
    .metric-card {
        background: linear-gradient(135deg, #1e212b 0%, #2a2d3e 100%);
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 8px 16px rgba(0,0,0,0.4);
        border: 1px solid #3a3f58;
        color: white;
        text-align: center;
        transition: transform 0.2s ease-in-out;
    }
    .metric-card:hover {
        transform: scale(1.02);
    }
    .metric-value {
        font-size: 42px;
        font-weight: 700;
        color: #00d2ff;
        margin: 10px 0;
        text-shadow: 0px 0px 10px rgba(0, 210, 255, 0.5);
    }
    .metric-label {
        font-size: 14px;
        color: #b0b5c9;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)

# Define data paths
# Assuming this script is in `scripts/`, we go up one level to root, then `data/results`
RESULTS_DIR = Path(__file__).parent.parent / "data" / "results"
METRICS_FILE = RESULTS_DIR / "traffic_metrics.csv"
POWER_FILE = RESULTS_DIR / "power_consumption.csv"

def load_data():
    try:
        if METRICS_FILE.exists() and POWER_FILE.exists():
            df_metrics = pd.read_csv(METRICS_FILE)
            df_power = pd.read_csv(POWER_FILE)
            
            # Convert timestamp to datetime
            df_metrics['timestamp'] = pd.to_datetime(df_metrics['timestamp'])
            df_power['timestamp'] = pd.to_datetime(df_power['timestamp'])
            return df_metrics, df_power
    except Exception as e:
        st.error(f"Error loading data: {e}")
    return None, None

def header():
    st.markdown("<h1 style='text-align: center; margin-bottom: 10px; font-size: 3rem;'>📡 AI-Driven 5G Energy Optimization Dashboard</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #a4a8b5; font-size: 1.2rem; margin-bottom: 40px;'>Real-time monitoring of energy consumption, traffic load, and AI Base Station control.</p>", unsafe_allow_html=True)

def main():
    header()
    
    # Sidebar
    st.sidebar.title("⚙️ Configuration")
    auto_refresh = st.sidebar.checkbox("Auto-Refresh (Live Data)", value=False)
    refresh_rate = st.sidebar.slider("Refresh Rate (seconds)", 1, 60, 5) if auto_refresh else None
    
    st.sidebar.markdown("---")
    
    if st.sidebar.button("▶️ Run Simulation Now", use_container_width=True):
        with st.spinner("Running 24-hr simulation..."):
            sim_script = Path(__file__).parent / "run_simulation.py"
            os.system(f"python \"{sim_script}\"")
            st.success("Simulation complete! Refreshing data...")
            time.sleep(1)
            st.rerun()

    # Load data
    df_metrics, df_power = load_data()
    
    if df_metrics is None or df_power is None or df_metrics.empty:
        st.warning("No data found. Please run the simulation first.")
        st.info(f"Looking for data in: `{RESULTS_DIR}`")
        if st.button("Generate Demo Data (Run Simulation)"):
            with st.spinner("Generating..."):
                sim_script = Path(__file__).parent / "run_simulation.py"
                os.system(f"python \"{sim_script}\"")
                st.rerun()
        return

    # Extract Latest Metrics
    latest_metrics = df_metrics.iloc[-1]
    latest_power = df_power.iloc[-1] if not df_power.empty else None
    
    peak_energy = df_power['total_power_w'].max() if latest_power is not None else df_metrics['energy_w'].max()
    curr_energy = latest_power['total_power_w'] if latest_power is not None else latest_metrics['energy_w']
    curr_latency = latest_metrics['latency_ms']
    
    # -----------------------------
    # KPI Row
    # -----------------------------
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Current Active Users</div>
            <div class="metric-value">{int(latest_metrics['active_users'])}</div>
            <div style='color: #00ffaa; font-size: 14px;'>Live Users Online</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Network Power</div>
            <div class="metric-value">{curr_energy:.0f} <span style="font-size:24px;">W</span></div>
            <div style='color: #00ffaa; font-size: 14px;'>Current Total Power</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Peak Power</div>
            <div class="metric-value">{peak_energy:.0f} <span style="font-size:24px;">W</span></div>
            <div style='color: #ffaa00; font-size: 14px;'>Max recorded in 24h</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Avg Latency</div>
            <div class="metric-value">{curr_latency:.1f} <span style="font-size:24px;">ms</span></div>
            <div style='color: #ff4a4a; font-size: 14px;'>QoS Metric</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br><br>", unsafe_allow_html=True)

    # -----------------------------
    # Visualization Charts
    # -----------------------------
    chart_col1, chart_col2 = st.columns(2)
    
    # Chart 1: Energy Consumption
    with chart_col1:
        st.markdown("### ⚡ Power Consumption Over Time")
        if latest_power is not None:
            fig1 = px.area(df_power, x='timestamp', y='total_power_w', 
                           color_discrete_sequence=['#00d2ff'],
                           template='plotly_dark')
        else:
            fig1 = px.area(df_metrics, x='timestamp', y='energy_w', 
                           color_discrete_sequence=['#00d2ff'],
                           template='plotly_dark')
        fig1.update_layout(margin=dict(l=0, r=0, t=20, b=0), height=350,
                           paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                           xaxis_title="", yaxis_title="Total Power (Watts)",
                           hovermode="x unified")
        # Add gradient to area plot
        fig1.update_traces(fillcolor='rgba(0, 210, 255, 0.2)', line=dict(width=3))
        st.plotly_chart(fig1, use_container_width=True)

    # Chart 2: Active Users
    with chart_col2:
        st.markdown("### 👥 Active Traffic Load (Users)")
        fig2 = px.line(df_metrics, x='timestamp', y='active_users', 
                       color_discrete_sequence=['#ff007f'], 
                       template='plotly_dark')
        fig2.update_layout(margin=dict(l=0, r=0, t=20, b=0), height=350,
                           paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                           xaxis_title="", yaxis_title="Active Users",
                           hovermode="x unified")
        fig2.update_traces(line=dict(width=3), fill='tozeroy', fillcolor='rgba(255, 0, 127, 0.1)')
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)
    
    chart_col3, chart_col4 = st.columns(2)
    
    # Chart 3: Network Throughput
    with chart_col3:
        st.markdown("### 🚀 Network Throughput")
        fig3 = px.bar(df_metrics, x='timestamp', y='data_mbps', 
                      color_discrete_sequence=['#ffaa00'],
                      template='plotly_dark')
        fig3.update_layout(margin=dict(l=0, r=0, t=20, b=0), height=300,
                           paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                           xaxis_title="", yaxis_title="Throughput (Mbps)")
        st.plotly_chart(fig3, use_container_width=True)
        
    # Chart 4: Latency Impact
    with chart_col4:
        st.markdown("### 📶 Quality of Service (Latency Impact)")
        fig4 = px.line(df_metrics, x='timestamp', y='latency_ms', 
                      color_discrete_sequence=['#ff3b3b'],
                      template='plotly_dark')
        # Add a baseline threshold line for max latency acceptable limit
        fig4.add_hline(y=1000, line_dash="dash", line_color="orange", annotation_text="Acceptable Latency Limit", annotation_position="top right")
        fig4.update_layout(margin=dict(l=0, r=0, t=20, b=0), height=300,
                           paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                           xaxis_title="", yaxis_title="Latency (ms)",
                           hovermode="x unified")
        fig4.update_traces(line=dict(width=2))
        st.plotly_chart(fig4, use_container_width=True)

    # System Logs / Raw Data viewer
    with st.expander("Show Raw Data Logs"):
        st.dataframe(df_metrics.tail(20), use_container_width=True)

    # Auto Refresh Logic
    if auto_refresh:
        time.sleep(refresh_rate)
        st.rerun()

if __name__ == "__main__":
    main()
