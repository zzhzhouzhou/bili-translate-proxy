@echo off
REM ============================================================
REM  Install: register autostart (current user) and launch now.
REM  After this, the proxy starts silently on every login and a
REM  watchdog keeps it alive. No window ever appears.
REM  (Delegates the real work to: python proxy.py install)
REM ============================================================
SETLOCAL
SET SCRIPT_DIR=%~dp0
CD /D "%SCRIPT_DIR%"

SET PYEXE=py
%PYEXE% --version >nul 2>&1
IF ERRORLEVEL 1 SET PYEXE=python

%PYEXE% proxy.py install
ECHO Done. You can close this window.
ENDLOCAL
pause
