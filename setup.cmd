@echo off
setlocal

if not exist .venv (
  python -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt

if not exist .env (
  copy .env.example .env >nul
  echo Created .env from .env.example
)

python admin_contacts.py init
python -m compileall -q .
python -m pytest -q

echo Setup complete. Edit .env, then run start.cmd
endlocal
