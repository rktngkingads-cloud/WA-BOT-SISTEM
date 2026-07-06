@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    call setup_windows.bat
    if errorlevel 1 exit /b 1
)

if not exist ".env" copy ".env.example" ".env" >nul

rem Reuse an existing local service to prevent an address-already-in-use error.
powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 1 | Out-Null; exit 0 } catch { exit 1 }" >nul 2>nul
if errorlevel 1 (
    start "WA Service" /D "%~dp0" cmd /k call run_server.bat
    timeout /t 2 /nobreak >nul
) else (
    echo WA Service sudah berjalan di http://127.0.0.1:8000
)

call run_monitor.bat
