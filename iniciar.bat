@echo off
setlocal
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
    echo Ambiente Python nao encontrado. Siga a instalacao no README.md.
    pause
    exit /b 1
)
"venv\Scripts\python.exe" run.py
if errorlevel 1 pause
