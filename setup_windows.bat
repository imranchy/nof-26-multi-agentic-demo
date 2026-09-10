@echo off
setlocal
cd /d "%~dp0"
if exist .venv\Scripts\python.exe (
  .venv\Scripts\python.exe -c "import sys; assert sys.version_info[:2] in [(3, 11), (3, 12)]" >nul 2>nul
  if not errorlevel 1 goto :venv_ready
  echo Removing incompatible virtual environment...
  rmdir /s /q .venv
)

py -3.12 -c "import sys; assert not hasattr(sys, '_is_gil_enabled') or sys._is_gil_enabled()" >nul 2>nul
if not errorlevel 1 (
  py -3.12 -m venv .venv
  goto :venv_ready
)

py -3.11 -c "import sys" >nul 2>nul
if not errorlevel 1 (
  py -3.11 -m venv .venv
  goto :venv_ready
)

echo ERROR: Standard Python 3.12 or 3.11 was not found.
echo The experimental free-threaded Python 3.13 build is not supported.
echo Install 64-bit Python 3.12 from https://www.python.org/downloads/windows/
pause
exit /b 1

:venv_ready
if not exist .venv\Scripts\python.exe (
  echo ERROR: Could not create .venv. Install Python with the py launcher and retry.
  pause
  exit /b 1
)
.venv\Scripts\python.exe -c "import sys; print('Using:', sys.executable); print(sys.version)"
.venv\Scripts\python.exe -m pip --isolated install --index-url https://pypi.org/simple --upgrade pip
.venv\Scripts\python.exe -m pip --isolated install --index-url https://pypi.org/simple --only-binary=:all: -r requirements.txt
if errorlevel 1 (
  echo ERROR: Dependency installation failed.
  pause
  exit /b 1
)
echo.
echo Installing the local Mistral model...
where ollama >nul 2>nul
if errorlevel 1 (
  echo ERROR: Ollama is not installed or is not on PATH.
  pause
  exit /b 1
)
ollama pull mistral:7b
echo.
echo Setup finished. The included ML models are already frozen for the demo.
echo Run validate_demo.bat once, then launch_demo.bat.
echo Only run train_models.bat if you intentionally want to regenerate the models.
pause
