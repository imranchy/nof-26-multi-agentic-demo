@echo off
setlocal
cd /d "%~dp0"

if exist .venv\Scripts\python.exe goto :venv_ready

py -3.12 -c "import sys" >nul 2>nul
if not errorlevel 1 (
  py -3.12 -m venv .venv
  goto :venv_ready
)

py -3.11 -c "import sys" >nul 2>nul
if not errorlevel 1 (
  py -3.11 -m venv .venv
  goto :venv_ready
)

echo ERROR: Python 3.12 or 3.11 was not found.
echo Install 64-bit Python and retry.
exit /b 1

:venv_ready
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
  echo ERROR: Dependency installation failed.
  exit /b 1
)

where ollama >nul 2>nul
if errorlevel 1 (
  echo WARNING: Ollama is not installed or is not on PATH.
  echo Install Ollama before running the live Mistral demo.
  exit /b 0
)

ollama pull mistral:7b

echo.
echo Setup complete.
echo Activate with: .venv\Scripts\activate
echo Verify with:   python -m pytest -q
echo Run demo with: python launcher.py
endlocal
