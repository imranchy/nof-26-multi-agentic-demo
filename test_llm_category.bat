@echo off
setlocal
cd /d "%~dp0"
if "%~1"=="" (
  echo Usage: test_llm_category.bat category_name
  echo Example: test_llm_category.bat traffic_prediction
  exit /b 1
)
if not exist .venv\Scripts\python.exe (
  echo ERROR: .venv is missing. Run setup_windows.bat first.
  exit /b 1
)
.venv\Scripts\python.exe -m tests.llm.evaluate --category %1
