@echo off
REM dzl - DayZ dev launcher. Hybrid: no args -> TUI, flags -> run & exit.
SET "VENV=%~dp0.venv\Scripts\python.exe"
IF NOT EXIST "%VENV%" (
    echo [dzl] venv missing. One-time setup:
    echo     python -m venv .venv
    echo     .venv\Scripts\python.exe -m pip install -r requirements.txt
    exit /b 1
)
REM Put the repo root on sys.path so `-m launcher` resolves from any CWD.
SET "PYTHONPATH=%~dp0;%PYTHONPATH%"
"%VENV%" -m launcher %*
