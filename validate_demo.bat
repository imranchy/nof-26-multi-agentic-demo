@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo ERROR: .venv is missing. Run setup_windows.bat first.
  pause
  exit /b 1
)
.venv\Scripts\python.exe -m pytest -q
if errorlevel 1 goto :error
.venv\Scripts\python.exe -m tests.llm.validate_gold
if errorlevel 1 goto :error
.venv\Scripts\python.exe -m scripts.build_validation_artifacts
if errorlevel 1 goto :error
.venv\Scripts\python.exe -m scripts.verify_install
if errorlevel 1 goto :error
echo Demo validation completed successfully.
pause
exit /b 0
:error
echo Validation failed. Copy the output for diagnosis.
pause
exit /b 1
