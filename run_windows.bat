@echo off
REM ============================================================
REM  Index-Translate local proxy - console launcher (debug view)
REM  Double-click to run in a visible window (Ctrl+C to stop).
REM  For silent/background use run_silent.bat instead.
REM ============================================================
SETLOCAL
SET SCRIPT_DIR=%~dp0
CD /D "%SCRIPT_DIR%"

SET PYEXE=py
%PYEXE% --version >nul 2>&1
IF ERRORLEVEL 1 SET PYEXE=python
%PYEXE% --version >nul 2>&1
IF ERRORLEVEL 1 GOTO NOPYTHON

echo Starting translation proxy (Ctrl+C to stop)...
echo.
%PYEXE% proxy.py serve %*
echo.
echo Proxy stopped.
pause
ENDLOCAL
GOTO :EOF

:NOPYTHON
echo [ERROR] Python not found. Install Python 3.8+ with "Add to PATH".
echo Download: https://www.python.org/downloads/
pause
ENDLOCAL
EXIT /B 1
