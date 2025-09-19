@echo off
echo ========================================
echo HYCOM Data Downloader - Web Interface
echo ========================================
echo.
echo Starting Flask web application...
echo.
echo The web interface will be available at:
echo http://localhost:5000
echo.
echo Press Ctrl+C to stop the server
echo ========================================
echo.

cd /d "%~dp0"
python run_app.py

pause
