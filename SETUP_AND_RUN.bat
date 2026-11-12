@echo off
setlocal enabledelayedexpansion
title Scuola dei Bambini - Auto Setup & Launcher
cd /d "%~dp0"
chcp 65001 >nul

echo ======================================================================
echo    SCUOLA DEI BAMBINI DI STA. TERESITA INTERNATIONAL MONTESSORI
echo             QR Payment & Campus E-Wallet System
echo ======================================================================
echo.

:: 1. Detect Python Command
set "PY_CMD="
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
if "%PY_CMD%"=="" if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if "%PY_CMD%"=="" if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
if "%PY_CMD%"=="" where py >nul 2>&1 && set "PY_CMD=py"
if "%PY_CMD%"=="" where python >nul 2>&1 && set "PY_CMD=python"

:: If Python is not installed, offer automatic installation
if "%PY_CMD%"=="" (
    echo [!] Python is not installed on this PC.
    echo [*] Attempting automatic Python 3.11 installation via Windows winget...
    echo.
    winget install -e --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo.
        echo ======================================================================
        echo  [X] Automatic installer could not finish.
        echo  Please install Python manually in 2 minutes:
        echo  1. Download Python: https://www.python.org/downloads/
        echo  2. IMPORTANT: Check the box "Add Python to PATH" during installation.
        echo  3. Re-run this SETUP_AND_RUN.bat file.
        echo ======================================================================
        pause
        exit /b 1
    )
    echo.
    echo [*] Python installed successfully! Restarting launcher...
    timeout /t 3 >nul
    "%~f0"
    exit /b 0
)

echo [*] Python detected: %PY_CMD%
echo.

:: 2. Check and install dependencies
echo [*] Checking required libraries (Flask, Pillow, PyMySQL, etc.)...
%PY_CMD% -m pip install -r requirements.txt --quiet --no-warn-script-location
if errorlevel 1 (
    echo [!] Notice: Standard install had warnings, running full pip install...
    %PY_CMD% -m pip install -r requirements.txt --no-warn-script-location
)

:: 3. Launch App and open browser
echo.
echo ======================================================================
echo    Starting Server...
echo    - Opening Web Browser to: http://127.0.0.1:5000/login_page
echo    - Press CTRL+C in this window when you want to stop the system.
echo ======================================================================
echo.

start http://127.0.0.1:5000/login_page
%PY_CMD% app.py

pause
