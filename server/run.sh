#!/bin/bash
cd "$(dirname "$0")"

echo "========================================"
echo "  E-Paper Display Server"
echo "========================================"
echo

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 not found"
    exit 1
fi

# Use a virtualenv: Homebrew/Debian Python refuse global pip installs (PEP 668)
if [ ! -x .venv/bin/python ]; then
    echo "Creating virtualenv in .venv..."
    python3 -m venv .venv || exit 1
fi

# Install dependencies
echo "Installing dependencies..."
.venv/bin/python -m pip install -r requirements.txt -q || exit 1

echo
echo "Starting server..."
echo
echo "Open in browser: http://localhost:8000"
echo
echo "Press Ctrl+C to stop"
echo "========================================"
echo

.venv/bin/python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
