@echo off
echo Starting Maharashtra Property Document Scraper...
echo.

REM Check if Python is installed
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Python is not installed or not in PATH. Please install Python 3.7+ and try again.
    pause
    exit /b 1
)

REM Check if requirements are installed
echo Checking and installing requirements...
pip install -r requirements.txt

REM Create directories if they don't exist
if not exist logs mkdir logs
if not exist downloads mkdir downloads

echo.
echo Choose an option:
echo 1. Run scraper once
echo 2. Run scheduler (continuous mode)
echo 3. Exit
echo.

set /p choice="Enter your choice (1-3): "

if "%choice%"=="1" (
    echo Running scraper once...
    python property_scraper.py
) else if "%choice%"=="2" (
    echo Running scheduler in continuous mode...
    echo Press Ctrl+C to stop the scheduler.
    python scheduler.py
) else if "%choice%"=="3" (
    echo Exiting...
    exit /b 0
) else (
    echo Invalid choice. Please try again.
    pause
    exit /b 1
)

pause