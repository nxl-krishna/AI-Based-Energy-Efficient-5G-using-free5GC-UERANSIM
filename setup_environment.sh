#!/bin/bash

# Setup script for AI-Based Energy Efficient 5G Project
# This script sets up the development environment

echo "=========================================="
echo "AI-Based Energy Efficient 5G Setup"
echo "=========================================="

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $python_version"

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "Installing dependencies..."
pip install -r requirements.txt

# Create necessary directories
echo "Creating data directories..."
mkdir -p data/traffic_logs
mkdir -p data/model_weights
mkdir -p data/results
mkdir -p data/logs

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Activate virtual environment:"
echo "   source venv/bin/activate"
echo ""
echo "2. Run the simulation:"
echo "   python scripts/run_simulation.py"
echo ""
echo "3. Evaluate results:"
echo "   python evaluation/performance_analyzer.py"
echo ""
