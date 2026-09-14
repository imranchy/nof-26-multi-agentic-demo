@echo off
setlocal

cd /d "%~dp0"

echo ============================================
echo   NoF 2026 Multi-Agent Digital Twin Demo
echo ============================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found.
    echo.
    echo Run setup_windows.bat first.
    echo.
    pause
    exit /b 1
)

echo Starting local DT Maanager...
echo.

".venv\Scripts\python.exe" -m streamlit run app\ui.py

if errorlevel 1 (
    echo.
    echo ERROR: Demo exited with an error.
    pause
)

endlocal