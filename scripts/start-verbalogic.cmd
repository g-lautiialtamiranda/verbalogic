@echo off
rem Starts VerbaLogic in the background (tray icon). Safe to run twice: the second copy just opens the popup.
if not exist "%~dp0..\.venv\Scripts\pythonw.exe" (
    echo VerbaLogic isn't installed yet. Run scripts\install.cmd first.
    pause
    exit /b 1
)
start "" "%~dp0..\.venv\Scripts\pythonw.exe" -m verbalogic
