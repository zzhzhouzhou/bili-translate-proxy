@echo off
REM ============================================================
REM  Index-Translate proxy - ONE-CLICK installer / controller
REM  Double-click -> a command window opens -> pick an action.
REM    1 = install / start  (asks about autostart, prints config)
REM    2 = stop now         (keeps autostart registration)
REM    3 = turn OFF completely (cancel autostart + stop)
REM ============================================================
SETLOCAL
SET SCRIPT_DIR=%~dp0
CD /D "%SCRIPT_DIR%"

SET PYEXE=py
%PYEXE% --version >nul 2>&1
IF ERRORLEVEL 1 SET PYEXE=python
%PYEXE% --version >nul 2>&1
IF ERRORLEVEL 1 GOTO NOPYTHON

:MENU
echo ============================================================
echo   Index-Translate local proxy
echo ============================================================
echo   1  Install / start      (setup wizard, asks about autostart)
echo   2  Stop now             (autostart registration is kept)
echo   3  Turn OFF completely  (cancel autostart + stop)
echo   4  Exit
echo ============================================================
echo.
echo Type 1, 2, 3 or 4 and press Enter (default is 1).
set "CHOICE="
set /p CHOICE=
if "%CHOICE%"=="" set "CHOICE=1"

if "%CHOICE%"=="1" GOTO DO_INSTALL
if "%CHOICE%"=="2" GOTO DO_STOP
if "%CHOICE%"=="3" GOTO DO_UNINSTALL
if "%CHOICE%"=="4" GOTO DONE
echo Invalid choice.
GOTO MENU

:DO_INSTALL
echo.
echo Starting setup wizard...
echo.
%PYEXE% proxy.py setup %*
echo.
GOTO ASK_AGAIN

:DO_STOP
echo.
%PYEXE% proxy.py stop
echo.
GOTO ASK_AGAIN

:DO_UNINSTALL
echo.
%PYEXE% proxy.py uninstall
echo.
echo The proxy is now OFF and will not start on next login.
echo.
GOTO ASK_AGAIN

:ASK_AGAIN
echo.
echo Return to the menu? (y = yes, anything else = exit)
set "AGAIN="
set /p AGAIN=
if /i "%AGAIN%"=="y" GOTO MENU
GOTO DONE

:DONE
ENDLOCAL
EXIT /B 0

:NOPYTHON
echo [ERROR] Python 3.8+ not found.
echo Download and install it (tick "Add python.exe to PATH"):
echo   https://www.python.org/downloads/
pause
ENDLOCAL
EXIT /B 1
