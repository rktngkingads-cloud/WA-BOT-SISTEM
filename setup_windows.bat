@echo off
setlocal

cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python tidak ditemukan di PATH. Install Python 3.11+ lalu buka CMD baru.
    exit /b 1
)

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul
if errorlevel 1 (
    echo Python 3.11+ belum siap dipakai dari CMD.
    echo Install Python dari https://www.python.org/downloads/windows/ dan centang "Add python.exe to PATH".
    echo Setelah install, tutup CMD lalu buka lagi.
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Membuat virtual environment...
    python -m venv .venv
    if errorlevel 1 exit /b 1
)

echo Meng-upgrade pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 exit /b 1

echo Menginstall dependency...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

if not exist ".env" (
    copy ".env.example" ".env" >nul
    echo File .env dibuat dari .env.example. Mode OFFLINE aktif. Token Meta tidak diperlukan untuk simulasi.
) else (
    echo File .env sudah ada, tidak ditimpa.
)

echo.
echo Setup selesai.
echo Jalankan: run_wa_bot.bat
