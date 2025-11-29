@echo off
echo ========================================
echo   E-Paper Display Server
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.9+
    pause
    exit /b 1
)

REM Check/install dependencies
echo Installing dependencies...
pip install -r requirements.txt -q

echo.
echo Starting server...
echo.
echo Open in browser: http://localhost:8000
echo.
echo Press Ctrl+C to stop
echo ========================================
echo.

python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000

