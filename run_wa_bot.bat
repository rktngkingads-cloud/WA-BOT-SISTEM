@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    call setup_windows.bat
    if errorlevel 1 exit /b 1
)

if not exist ".env" copy ".env.example" ".env" >nul

start "WA Service" /D "%~dp0" cmd /k ".venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000"
timeout /t 2 /nobreak >nul
call run_monitor.bat
