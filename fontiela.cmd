@echo off
where pythonw.exe >nul 2>&1
if errorlevel 1 (
    echo Python bulunamadi. Python 3 kurulumu gerekli.
    pause
    exit /b 1
)
start "" pythonw.exe "%~dp0app.py"
