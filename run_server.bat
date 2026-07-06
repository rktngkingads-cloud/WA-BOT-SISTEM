@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment belum ada. Jalankan setup_windows.bat dulu.
    exit /b 1
)

if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo File .env dibuat dalam mode OFFLINE.
)

".venv\Scripts\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 8000
