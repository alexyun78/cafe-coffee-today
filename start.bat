@echo off
cls

echo ================================
echo Cafe Today Coffee - Starting Server
echo ================================
echo.

REM Check if packages are installed
python -c "import flask" 2>nul
if errorlevel 1 (
    echo [INFO] Installing required packages...
    pip install -r requirements.txt
    echo.
)

REM Start server
echo [INFO] Starting server...
echo [INFO] Access URL: http://localhost:5000
echo.
echo Press Ctrl+C to stop the server.
echo.

python app.py

pause
