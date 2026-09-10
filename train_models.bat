@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo ERROR: .venv is missing. Run setup_windows.bat first.
  pause
  exit /b 1
)
echo.
echo WARNING: Retraining is NOT required for the NoF demo.
echo This will replace the frozen XGBoost and Random Forest model files.
set /p confirm=Type YES to continue: 
if /I not "%confirm%"=="YES" (
  echo Cancelled. Frozen models were left unchanged.
  pause
  exit /b 0
)
.venv\Scripts\python.exe -m scripts.train_forecaster
if errorlevel 1 goto :error
.venv\Scripts\python.exe -m scripts.train_classifier
if errorlevel 1 goto :error
.venv\Scripts\python.exe -m scripts.build_validation_artifacts
if errorlevel 1 goto :error
echo Retraining and validation-artifact generation completed.
pause
exit /b 0
:error
echo Training failed. Copy the complete output and send it for diagnosis.
pause
exit /b 1
