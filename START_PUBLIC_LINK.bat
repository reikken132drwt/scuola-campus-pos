@echo off
cd /d "%~dp0"
title Scuola dei Bambini - Client Demo Public Link Launcher
color 0A
echo ======================================================================
echo    Scuola dei Bambini - Client Demo Public Link Launcher
echo ======================================================================
echo.

:: Check if server is running on port 5000
netstat -ano | findstr /R /C:":5000 " >nul 2>&1
if errorlevel 1 (
    echo [!] Server is not running yet. Starting RUN_SYSTEM.bat...
    start "" cmd /c "RUN_SYSTEM.bat"
    timeout /t 4 >nul
) else (
    echo [*] Local server is active on Port 5000.
)

echo [*] Starting secure Cloudflare Tunnel to your Flask app...
echo [*] Look for the line starting with: https://xxxx.trycloudflare.com below!
echo.
echo [*] Send that link to your client.
echo [*] Keep this window open while your client is browsing.
echo ======================================================================
echo.
"%~dp0cloudflared.exe" tunnel --url http://127.0.0.1:5000
pause
