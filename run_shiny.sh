#!/bin/bash

# Run Shiny Dashboard for Portfolio Risk Management
# Usage: ./run_shiny.sh

echo "🚀 Starting Portfolio Risk Management Dashboard (Shiny)"
echo "=========================================="
echo ""
echo "Navigate to: http://localhost:8000"
echo "Press Ctrl+C to stop"
echo ""

cd "$(dirname "$0")" || exit
export PYTHONPATH="${PYTHONPATH}:$(pwd)/portfolio_risk_system/python"

shiny run shiny_app.py --reload --port 8000
