@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" call setup_windows.bat
if errorlevel 1 exit /b 1
if not exist ".env" copy ".env.example" ".env" >nul
if not exist "batch_contacts.csv" copy "batch_contacts.example.csv" "batch_contacts.csv" >nul
".venv\Scripts\python.exe" batch_queue.py --file batch_contacts.csv
pause
