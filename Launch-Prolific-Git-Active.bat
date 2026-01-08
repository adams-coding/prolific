@echo off
setlocal enabledelayedexpansion

REM Prolific: Git Active — one-click UI launcher for Windows
REM - Creates .venv if missing
REM - Installs this project into the venv (editable)
REM - Launches the UI

cd /d "%~dp0"

where py >nul 2>nul
if %errorlevel% neq 0 (
  echo ERROR: Python launcher 'py' not found.
  echo Install Python 3.11+ from python.org and check "Add Python to PATH".
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  py -3 -m venv .venv
  if %errorlevel% neq 0 (
    echo ERROR: Failed to create venv.
    pause
    exit /b 1
  )
)

echo Installing/Updating app in venv...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install -e . 
if %errorlevel% neq 0 (
  echo ERROR: pip install failed.
  pause
  exit /b 1
)

echo Launching UI...
REM Launch UI detached so the CMD window doesn't linger.
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" -m prolific_agent.cli ui
  exit /b 0
)

REM Fallback: pythonw missing (shouldn't happen). Run in console and pause on error only.
".venv\Scripts\python.exe" -m prolific_agent.cli ui
set RC=%errorlevel%
if %RC% neq 0 (
  echo.
  echo ERROR: UI failed to start (exit code %RC%).
  pause
)
exit /b %RC%

endlocal

