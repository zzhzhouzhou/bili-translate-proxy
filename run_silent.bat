@echo off
REM ============================================================
REM  Index-Translate local proxy - SILENT launcher
REM  Delegates to start_hidden.vbs (no console window).
REM  The server runs in the background until you stop it.
REM ============================================================
SETLOCAL
SET SCRIPT_DIR=%~dp0
cscript //nologo "%SCRIPT_DIR%start_hidden.vbs"
EXIT /B
