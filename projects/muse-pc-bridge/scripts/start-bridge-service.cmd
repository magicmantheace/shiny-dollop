@echo off
rem muse-pc-bridge — start the SUPERVISED agent (v1 service form).
rem The supervisor console stays visible on purpose: it is the
rem indicator that the bridge is running, and closing it stops the
rem agent — that is the kill switch. The supervisor restarts the
rem agent if it crashes and applies staged updates with automatic
rem rollback (see agent\supervisor.py).
setlocal
cd /d "%~dp0..\agent"
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  py -3 supervisor.py
) else (
  python supervisor.py
)
endlocal
