@echo off
REM Stop the background proxy (and its watchdog).
SETLOCAL
taskkill /F /FI "IMAGENAME eq python.exe" /FI "WINDOWTITLE eq *proxy.py*" >nul 2>&1
taskkill /F /FI "IMAGENAME eq pythonw.exe" >nul 2>&1
taskkill /F /FI "IMAGENAME eq py.exe" >nul 2>&1
ECHO Stop signal sent. The proxy should shut down shortly.
ENDLOCAL
pause
