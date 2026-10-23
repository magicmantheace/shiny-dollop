@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [INFO] Project .venv not found; cinematic model install only needs PowerShell and the media Hugging Face CLI.
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install-underreach-cinematic-image-model.ps1"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
    echo.
    echo [ERROR] Cinematic image model installation failed with exit code %RC%.
    exit /b %RC%
)

echo.
echo [OK] Underreach cinematic image model is ready.
exit /b 0
