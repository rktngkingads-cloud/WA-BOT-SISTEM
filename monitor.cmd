@echo off
setlocal EnableExtensions

if not exist .venv\Scripts\python.exe (
  echo Jalankan setup.cmd terlebih dahulu.
  exit /b 1
)

:refresh
cls
echo ================================================================
echo                         WA BOT LOCAL MONITOR
echo ================================================================
echo.
echo [SESSION]
curl -s --max-time 2 http://127.0.0.1:8000/health
echo.
echo.
echo [CONTACTS]
.venv\Scripts\python.exe admin_contacts.py list --limit 19
echo.
echo [MESSAGE STATUS]
.venv\Scripts\python.exe admin_messages.py summary
echo.
echo [RECENT ACTIVITY]
.venv\Scripts\python.exe admin_messages.py list --limit 12
echo.
echo Read-only monitor. Press Ctrl+C to close.
timeout /t 2 /nobreak >nul
goto refresh
