@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo ERROR: .venv is missing. Run setup_windows.bat first.
  pause
  exit /b 1
)
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --name NoF2026MultiAgentDemo --collect-all streamlit --collect-all plotly --add-data "app;app" --add-data "data;data" --add-data "models;models" launcher.py
echo Build output: dist\NoF2026MultiAgentDemo\NoF2026MultiAgentDemo.exe
pause
