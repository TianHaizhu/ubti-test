@echo off
chcp 65001 >nul
cd /d "%~dp0"
py -3.11 -m venv .venv
if errorlevel 1 (
  echo Failed to create venv. Please install Python 3.11 and enable Add Python to PATH.
  pause
  exit /b 1
)
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\pip install -r requirements.txt
if errorlevel 1 (
  echo Dependency installation failed.
  pause
  exit /b 1
)
echo Setup complete. Double-click run.bat.
pause
