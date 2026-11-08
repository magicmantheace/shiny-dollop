@echo off
rem muse-pc-bridge -- start the HEADLESS CORE (v1.1 boot form).
rem Runs the supervisor with --headless under pythonw: no console,
rem no window, no GUI work of any kind. The supervisor's prints go
rem to agent\state\supervisor-core.log. Started at machine boot by
rem the "Muse PC Bridge (core)" Scheduled Task (SYSTEM) -- install
rem or remove that task with scripts\bridge-core.ps1.
rem The avatar (start-bridge-gui.cmd at logon) attaches to this core
rem display-only; it does not own it. Stop the core with
rem bridge-core.ps1 -Action stop or by disabling the task.
setlocal
cd /d "%~dp0..\agent"
where pyw >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  pyw -3 supervisor.py --headless
) else (
  pythonw supervisor.py --headless
)
endlocal
