@echo off
REM Desktop Friend PC agent launcher (Windows).
REM Creates a virtual environment on first run, installs dependencies, then starts the agent.
REM Extra arguments are passed through, e.g.  start.bat --headless
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")

if not exist .venv (
  echo Creating virtual environment ^(.venv^)...
  %PY% -m venv .venv || (echo Python 3.10+ is required: https://www.python.org/downloads/ & pause & exit /b 1)
)
call .venv\Scripts\activate.bat

if not exist .venv\.deps-installed (
  echo Installing dependencies, this takes a minute the first time...
  python -m pip install --quiet --upgrade pip
  python -m pip install --quiet -r requirements.txt || (pause & exit /b 1)
  echo ok> .venv\.deps-installed
)

if not exist .env copy .env.example .env >nul
python -m desktop_friend %*
if errorlevel 1 pause
