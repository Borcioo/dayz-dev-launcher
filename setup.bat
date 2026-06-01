@echo off
REM ============================================================
REM  dzl - DayZ dev launcher : one-click setup
REM  Double-click this file. It checks Python, creates the
REM  virtual environment and installs everything dzl needs.
REM ============================================================
setlocal
cd /d "%~dp0"

echo ============================================================
echo   dzl - DayZ dev launcher : setup
echo ============================================================
echo.

REM --- 1) Python on PATH? ---------------------------------------------------
where python >nul 2>&1
if errorlevel 1 (
    echo [X] Python was not found.
    echo.
    echo     Install Python 3.11 or newer from:
    echo         https://www.python.org/downloads/
    echo     IMPORTANT: on the first install screen, tick
    echo         "Add python.exe to PATH"
    echo     Then run this setup.bat again.
    echo.
    pause
    exit /b 1
)

REM --- 2) Python 3.11+ ? ----------------------------------------------------
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 (
    echo [X] Python 3.11 or newer is required. You have:
    python --version
    echo     Get a newer version from https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)
echo [ok] Found Python:
python --version
echo.

REM --- 3) virtual environment ----------------------------------------------
if exist ".venv\Scripts\python.exe" (
    echo [ok] Virtual environment already exists.
) else (
    echo [..] Creating virtual environment in .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [X] Could not create the virtual environment.
        pause
        exit /b 1
    )
)
echo.

REM --- 4) dependencies ------------------------------------------------------
echo [..] Installing dependencies (textual, click, pytest) ...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>&1
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [X] Installing dependencies failed. Check your internet connection
    echo     and run setup.bat again.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   All set!  Start the launcher by double-clicking:
echo       dzl.bat
echo   (or run  dzl.bat  in a terminal)
echo ============================================================
echo.
pause
