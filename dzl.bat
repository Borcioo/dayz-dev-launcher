@echo off
REM dzl - DayZ dev launcher. Hybrid: no args -> TUI, flags -> run & exit.
SET "VENV=%~dp0.venv\Scripts\python.exe"
IF NOT EXIST "%VENV%" (
    echo [dzl] Not set up yet. Double-click setup.bat first
    echo       ^(it installs everything^). Then run dzl.bat again.
    pause
    exit /b 1
)
REM Put the repo root on sys.path so `-m launcher` resolves from any CWD.
SET "PYTHONPATH=%~dp0;%PYTHONPATH%"
"%VENV%" -m launcher %*
