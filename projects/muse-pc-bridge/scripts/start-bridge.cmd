@echo off
rem muse-pc-bridge launcher.
rem The visible console IS the running indicator: while this window is
rem open, the agent is running. Closing it (or pressing Ctrl+C) is the
rem kill switch — the agent stops and Muse loses access immediately.
setlocal
cd /d "%~dp0..\agent"
echo Starting muse-pc-bridge agent...
python bridge_agent.py
echo.
echo [bridge] Agent stopped.
pause
endlocal
