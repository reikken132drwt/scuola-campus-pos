@echo off
cd /d "%~dp0"
chcp 65001 >nul
title Scuola dei Bambini - QR Student System

echo ======================================================================
echo    SCUOLA DEI BAMBINI DI STA. TERESITA INTERNATIONAL MONTESSORI
echo             QR Payment & Campus E-Wallet System
echo ======================================================================
echo.

:: Detect Python command
set "PY_CMD="
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    set "PY_CMD=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
) else (
    where py >nul 2>&1 && set "PY_CMD=py"
    if "%PY_CMD%"=="" where python >nul 2>&1 && set "PY_CMD=python"
)

echo.
echo [*] Launching Server...
echo [*] Opening Web Browser to http://127.0.0.1:5000/login_page
start http://127.0.0.1:5000/login_page

echo.
echo ======================================================================
echo    System is now running! 
echo    - Local Access: http://127.0.0.1:5000/login_page
echo    - Press CTRL+C in this window to stop the server.
echo ======================================================================
echo.

%PY_CMD% app.py

pause
