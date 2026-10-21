@echo off
REM Stop the background proxy using the official 'stop' command.
REM This only stops THIS project's watchdog + proxy worker; other Python
REM programs are never touched.
SETLOCAL
SET "DIR=%~dp0"
SET "PY=py"
where py >nul 2>&1 || SET "PY=python"

"%PY%" "%DIR%proxy.py" stop
ECHO.
ECHO Done. The proxy is stopped (autostart, if any, is still registered).
ECHO To also cancel autostart, run uninstall.bat.
pause
ENDLOCAL
