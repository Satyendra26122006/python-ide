@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=%~dp0..\..\.venv\Scripts\python.exe"
)
if not exist "%PYTHON_EXE%" (
    set "PYTHON_EXE=python"
)

echo Starting Python IDE...
"%PYTHON_EXE%" launch.py

if errorlevel 1 (
    echo.
    echo Failed to start the IDE.
    echo Install the requirements first with: pip install -r requirements.txt
    pause
)
