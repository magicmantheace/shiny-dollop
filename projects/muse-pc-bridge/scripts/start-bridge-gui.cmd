@echo off
rem muse-pc-bridge -- start the GUI (avatar display) supervisor.
rem The floating avatar window is the visible indicator that the
rem bridge is running, and stopping it (x or right-click > Stop
rem bridge) stops the supervisor AND the agent -- that is the kill
rem switch, same as closing the console in the other forms. The
rem supervisor still restarts the agent on crash and applies staged
rem updates with automatic rollback (see agent\supervisor_gui.py).
rem pythonw forms no console window; the supervisor's own prints go
rem to state\supervisor-gui.log beside its status files.
setlocal
cd /d "%~dp0..\agent"
where pyw >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  start "" pyw -3 supervisor_gui.py
) else (
  start "" pythonw supervisor_gui.py
)
endlocal
