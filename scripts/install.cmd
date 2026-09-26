@echo off
rem Sets up VerbaLogic on this PC: creates .venv next to the project and installs the app into it.
rem Safe to run again: use it after "git pull" to update.
setlocal
set "ROOT=%~dp0.."
set "CHECK=import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"

set "PY="
py -3 -c "%CHECK%" >nul 2>&1 && set "PY=py -3"
if not defined PY python -c "%CHECK%" >nul 2>&1 && set "PY=python"
if not defined PY (
    echo VerbaLogic needs Python 3.11 or newer, and it wasn't found.
    echo Install it from https://www.python.org/downloads/ ^(tick "Add python.exe to PATH"^), then run this again.
    goto :fail
)

if not exist "%ROOT%\.venv\Scripts\python.exe" (
    echo Creating the Python environment...
    %PY% -m venv "%ROOT%\.venv" || goto :fail
)

echo Installing VerbaLogic...
"%ROOT%\.venv\Scripts\python.exe" -m pip install --disable-pip-version-check --quiet --upgrade pip || goto :fail
"%ROOT%\.venv\Scripts\python.exe" -m pip install --disable-pip-version-check --quiet -e "%ROOT%" || goto :fail

echo.
echo Done. Start VerbaLogic with scripts\start-verbalogic.cmd
echo Then select text anywhere and press Ctrl+Alt+D.
if "%~1"=="" pause
exit /b 0

:fail
echo.
echo Setup failed. See the messages above.
if "%~1"=="" pause
exit /b 1
