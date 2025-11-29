#!/bin/bash
echo "========================================"
echo "  E-Paper Display Server"
echo "========================================"
echo

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 not found"
    exit 1
fi

# Install dependencies
echo "Installing dependencies..."
pip3 install -r requirements.txt -q

echo
echo "Starting server..."
echo
echo "Open in browser: http://localhost:8000"
echo
echo "Press Ctrl+C to stop"
echo "========================================"
echo

python3 -m uvicorn app:app --reload --host 0.0.0.0 --port 8000

