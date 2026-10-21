@echo off
REM Fully turn the proxy OFF: cancel autostart, then stop the running processes.
REM Safe to run multiple times. Does not delete any files.
SETLOCAL
SET "DIR=%~dp0"
SET "PY=py"
where py >nul 2>&1 || SET "PY=python"

ECHO ============================================================
ECHO  Turn OFF the Index-Translate local proxy
ECHO ============================================================
ECHO.
"%PY%" "%DIR%proxy.py" uninstall
ECHO.
ECHO ============================================================
ECHO  The proxy is now OFF and will NOT start on next login.
ECHO  Your translation plugin will need another service, or you can
ECHO  re-enable this later by double-clicking setup.bat.
ECHO ============================================================
pause
ENDLOCAL
