@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo ERROR: .venv is missing. Run setup_windows.bat first.
  pause
  exit /b 1
)
.venv\Scripts\python.exe launcher.py
if errorlevel 1 pause
