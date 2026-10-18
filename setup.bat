@echo off
REM ============================================================
REM  Index-Translate proxy - ONE-CLICK interactive setup
REM  Double-click -> a command window opens -> auto setup ->
REM  asks about autostart -> prints API URL / Key / Model.
REM ============================================================
SETLOCAL
SET SCRIPT_DIR=%~dp0
CD /D "%SCRIPT_DIR%"

SET PYEXE=py
%PYEXE% --version >nul 2>&1
IF ERRORLEVEL 1 SET PYEXE=python
%PYEXE% --version >nul 2>&1
IF ERRORLEVEL 1 GOTO NOPYTHON

echo Starting setup wizard...
echo.
%PYEXE% proxy.py setup %*
echo.
ENDLOCAL
GOTO :EOF

:NOPYTHON
echo [ERROR] Python 3.8+ not found.
echo Download and install it (tick "Add python.exe to PATH"):
echo   https://www.python.org/downloads/
pause
ENDLOCAL
EXIT /B 1
