@echo off
setlocal EnableExtensions

if not exist .venv\Scripts\python.exe (
  echo Virtual environment belum tersedia. Jalankan setup.cmd terlebih dahulu.
  exit /b 1
)

if not exist .env (
  echo File .env belum tersedia. Jalankan setup.cmd lalu isi credential.
  exit /b 1
)

.venv\Scripts\python.exe -m uvicorn app:app --host 0.0.0.0 --port 8000 --env-file .env
endlocal
