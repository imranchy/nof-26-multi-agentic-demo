@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo ERROR: .venv is missing. Run setup_windows.bat first.
  pause
  exit /b 1
)
.venv\Scripts\python.exe -m scripts.train_forecaster
if errorlevel 1 goto :error
.venv\Scripts\python.exe -m scripts.train_classifier
if errorlevel 1 goto :error
.venv\Scripts\python.exe -m scripts.verify_install
if errorlevel 1 goto :error
echo Training and verification completed.
pause
exit /b 0
:error
echo Training failed. Copy the complete output and send it for diagnosis.
pause
exit /b 1
