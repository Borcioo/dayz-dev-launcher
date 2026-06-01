@echo off
REM ============================================================
REM  dzl - DayZ dev launcher : one-click setup
REM  Double-click this file. It checks Python (offering to
REM  install it), creates the virtual environment, installs
REM  dependencies and puts 'dzl' on your PATH.
REM ============================================================
setlocal
cd /d "%~dp0"

echo ============================================================
echo   dzl - DayZ dev launcher : setup
echo ============================================================
echo.

REM --- 1) Python 3.11+ present? --------------------------------------------
where python >nul 2>&1
if errorlevel 1 goto need_python
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
if errorlevel 1 goto need_python
goto have_python

:need_python
echo [X] Python 3.11+ was not found.
echo.
where winget >nul 2>&1
if errorlevel 1 goto manual_python
choice /C YN /M "    Install Python 3.12 automatically via winget"
if errorlevel 2 goto manual_python
echo.
echo [..] Installing Python 3.12 via winget (this can take a minute) ...
winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
if errorlevel 1 (
    echo [X] winget could not install Python.
    goto manual_python
)
echo.
echo [ok] Python installed. Please CLOSE this window and run setup.bat again
echo      ^(a fresh terminal is needed so Python is on the PATH^).
echo.
pause
exit /b 0

:manual_python
echo     Install Python 3.11 or newer from:
echo         https://www.python.org/downloads/
echo     IMPORTANT: on the first install screen, tick
echo         "Add python.exe to PATH"
echo     Then run this setup.bat again.
echo.
pause
exit /b 1

:have_python
echo [ok] Found Python:
python --version
echo.

REM --- 2) virtual environment ----------------------------------------------
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

REM --- 3) dependencies ------------------------------------------------------
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

REM --- 4) put this folder on the user PATH (so you can type 'dzl') ----------
echo [..] Adding this folder to your user PATH (for the 'dzl' command) ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0_path.ps1" "%~dp0"

echo.
echo ============================================================
echo   All set!
echo   Open a NEW terminal, then just run:   dzl
echo   (or double-click dzl.bat here anytime)
echo ============================================================
echo.
pause
