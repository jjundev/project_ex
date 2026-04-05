@echo off
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python gui.py
) else (
    python gui.py
)
pause
