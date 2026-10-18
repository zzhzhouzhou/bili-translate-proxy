' ============================================================
'  Index-Translate local proxy - SILENT launcher (no window)
'  Launches the watchdog via the system python launcher so it is
'  path-agnostic (no hardcoded interpreter path). The watchdog
'  keeps the proxy alive and restarts it if it ever dies, and
'  is what gets registered for autostart.
' ============================================================
Option Explicit
Dim WshShell, fso, scriptDir, py, logOut, logErr, cmd
Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

py = "py"          ' Windows Python launcher (resolves any installed python)
If WshShell.Run("cmd /c where py >nul 2>&1", 0, True) <> 0 Then py = "python"

logOut = scriptDir & "\proxy.out.log"
logErr = scriptDir & "\proxy.err.log"

' Run via cmd /c so stdout/stderr redirect to files. Window style 0 = hidden.
cmd = "%COMSPEC% /c """"" & py & """ """ & scriptDir & "\watchdog.py"" > """ & logOut & """ 2> """ & logErr & """"

WshShell.Run cmd, 0, False
Set WshShell = Nothing
