@echo off
setlocal
chcp 65001 >nul
title WA Contact ^& Message Monitor
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment belum ada. Menjalankan setup...
    call setup_windows.bat
    if errorlevel 1 exit /b 1
)

if not exist ".env" copy ".env.example" ".env" >nul

".venv\Scripts\python.exe" wa_monitor.py
