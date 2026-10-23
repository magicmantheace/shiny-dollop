@echo off
setlocal EnableExtensions EnableDelayedExpansion

title Underreach Full Local Media Pipeline Installer

cd /d "%~dp0"
set "REPO_ROOT=%CD%"

if not exist "%REPO_ROOT%\pyproject.toml" (
    echo [ERROR] Run this installer from the root of the Crawl repository.
    exit /b 1
)
if not exist "%REPO_ROOT%\dashboard\package-lock.json" (
    echo [ERROR] Crawl dashboard package-lock.json was not found.
    exit /b 1
)

for %%I in ("%REPO_ROOT%\..") do set "REPO_PARENT=%%~fI"
if defined UNDERREACH_MEDIA_HOME (
    set "MEDIA_HOME=%UNDERREACH_MEDIA_HOME%"
) else (
    set "MEDIA_HOME=%REPO_PARENT%\CrawlMedia"
)

set "COMFY_HOME=%MEDIA_HOME%\ComfyUI"
set "MEDIA_VENV=%MEDIA_HOME%\python\.venv"
set "KOKORO_HOME=%MEDIA_HOME%\models\Kokoro-82M"
set "OLLAMA_MODEL_HOME=%MEDIA_HOME%\models\ollama"
set "HF_STAGE=%MEDIA_HOME%\hf-stage"
set "HF_CACHE=%MEDIA_HOME%\huggingface-cache"
set "WORKFLOW_HOME=%MEDIA_HOME%\workflows"
set "AUDIO_HOME=%MEDIA_HOME%\audio"
set "OUTPUT_HOME=%MEDIA_HOME%\output"

set "HF_HOME=%HF_CACHE%"
set "HF_XET_HIGH_PERFORMANCE=1"
set "OLLAMA_MODELS=%OLLAMA_MODEL_HOME%"
set "WRITER_MODEL=qwen3:8b"
set "VERIFIER_MODEL=qwen3:4b"

echo.
echo ============================================================
echo  UNDERREACH FULL LOCAL MEDIA PIPELINE INSTALLER
echo ============================================================
echo Repo:       %REPO_ROOT%
echo Media home: %MEDIA_HOME%
echo.
echo This installs/configures:
echo   - Git
 echo   - Python 3.12
 echo   - Node.js LTS + locked React/Vite dashboard dependencies
 echo   - Microsoft Visual C++ runtime
 echo   - FFmpeg / ffprobe
 echo   - Ollama with model storage under CrawlMedia
 echo   - eSpeak NG
 echo   - Crawl backend + test dependencies
 echo   - Dedicated Python 3.12 Kokoro/Hugging Face environment
 echo   - ComfyUI + NVIDIA CUDA PyTorch
 echo   - Qwen3 8B writer
 echo   - Qwen3 4B verifier
 echo   - SDXL Base 1.0 image model
 echo   - Wan 2.2 TI2V 5B video model + text encoder + VAE
 echo   - Kokoro-82M v1.0 + voices
 echo   - Official SDXL and Wan ComfyUI workflows
 echo.
echo Approximate model weight download: 34 GB.
echo Recommended free space before install: 50 GB or more.
echo The installer is idempotent and safe to rerun.
echo.

call :check_disk "%MEDIA_HOME%" 50
if errorlevel 1 goto :fail

where winget >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Windows Package Manager ^(winget^) is required.
    echo Install/update "App Installer" from Microsoft Store, then rerun this file.
    goto :fail
)

call :winget_install "Git.Git" "Git"
if errorlevel 1 goto :fail
call :winget_install "Python.Python.3.12" "Python 3.12"
if errorlevel 1 goto :fail
call :winget_install "OpenJS.NodeJS.LTS" "Node.js LTS"
if errorlevel 1 goto :fail
call :winget_install "Microsoft.VCRedist.2015+.x64" "Microsoft Visual C++ Runtime"
if errorlevel 1 goto :fail
call :winget_install "Gyan.FFmpeg" "FFmpeg"
if errorlevel 1 goto :fail
call :winget_install "Ollama.Ollama" "Ollama"
if errorlevel 1 goto :fail
call :winget_install "eSpeak-NG.eSpeak-NG" "eSpeak NG"
if errorlevel 1 goto :fail

set "PATH=%LOCALAPPDATA%\Microsoft\WinGet\Links;%ProgramFiles%\Git\cmd;%ProgramFiles%\nodejs;%LOCALAPPDATA%\Programs\Ollama;%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%ProgramFiles%\eSpeak NG;%PATH%"
call :ensure_user_path "%LOCALAPPDATA%\Microsoft\WinGet\Links"
call :ensure_user_path "%ProgramFiles%\eSpeak NG"
call :set_user_env "OLLAMA_MODELS" "%OLLAMA_MODEL_HOME%"

call :resolve_python312
if errorlevel 1 goto :fail
call :verify_node20
if errorlevel 1 goto :fail
call :check_nvidia
if errorlevel 1 goto :fail

if not exist "%MEDIA_HOME%" mkdir "%MEDIA_HOME%"
if not exist "%OLLAMA_MODEL_HOME%" mkdir "%OLLAMA_MODEL_HOME%"
if not exist "%HF_CACHE%" mkdir "%HF_CACHE%"


echo.
echo [STEP] Creating/updating Crawl project virtual environment
if not exist "%REPO_ROOT%\.venv\Scripts\python.exe" (
    "%PY312%" -m venv "%REPO_ROOT%\.venv"
    if errorlevel 1 goto :fail
)
set "PROJECT_PY=%REPO_ROOT%\.venv\Scripts\python.exe"

"%PROJECT_PY%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3,12) else 1)"
if errorlevel 1 (
    echo [ERROR] Existing .venv uses Python older than 3.12.
    echo Delete "%REPO_ROOT%\.venv" and rerun the installer.
    goto :fail
)
"%PROJECT_PY%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :fail
"%PROJECT_PY%" -m pip install -e ".[test]"
if errorlevel 1 goto :fail

if not exist "%REPO_ROOT%\.env" if exist "%REPO_ROOT%\.env.example" (
    copy /Y "%REPO_ROOT%\.env.example" "%REPO_ROOT%\.env" >nul
    echo [OK] Created .env from .env.example. Review secrets/settings before exposing the API.
)


echo.
echo [STEP] Installing locked dashboard dependencies
pushd "%REPO_ROOT%\dashboard"
call npm ci
if errorlevel 1 (
    popd
    goto :fail
)
call npm run build
if errorlevel 1 (
    popd
    goto :fail
)
popd


echo.
echo [STEP] Creating/updating dedicated Python 3.12 media environment
if not exist "%MEDIA_VENV%\Scripts\python.exe" (
    "%PY312%" -m venv "%MEDIA_VENV%"
    if errorlevel 1 goto :fail
)
set "MEDIA_PY=%MEDIA_VENV%\Scripts\python.exe"
"%MEDIA_PY%" -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3,12) else 1)"
if errorlevel 1 (
    echo [ERROR] Media virtual environment is not Python 3.12.
    echo Delete "%MEDIA_VENV%" and rerun the installer.
    goto :fail
)
"%MEDIA_PY%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :fail
"%MEDIA_PY%" -m pip install --upgrade "huggingface_hub[hf_xet]" ollama "kokoro>=0.9.2" soundfile "misaki[en]"
if errorlevel 1 goto :fail

set "HF_EXE=%MEDIA_VENV%\Scripts\hf.exe"
if not exist "%HF_EXE%" set "HF_EXE=%MEDIA_VENV%\Scripts\huggingface-cli.exe"
if not exist "%HF_EXE%" (
    echo [ERROR] Hugging Face CLI was not installed into the media virtual environment.
    goto :fail
)


echo.
echo [STEP] Verifying FFmpeg media capabilities
where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo [ERROR] ffmpeg is still not visible on PATH.
    echo WinGet link directory: %LOCALAPPDATA%\Microsoft\WinGet\Links
    goto :fail
)
where ffprobe >nul 2>&1
if errorlevel 1 (
    echo [ERROR] ffprobe is still not visible on PATH.
    goto :fail
)
ffmpeg -hide_banner -encoders 2>&1 | findstr /I /C:"libx264" >nul
if errorlevel 1 (
    echo [ERROR] FFmpeg build is missing libx264.
    goto :fail
)
for %%F in (subtitles xfade zoompan loudnorm afade amix sidechaincompress) do (
    ffmpeg -hide_banner -filters 2>&1 | findstr /I /C:"%%F" >nul
    if errorlevel 1 (
        echo [ERROR] FFmpeg build is missing required filter: %%F
        goto :fail
    )
)
echo [OK] FFmpeg has the required Phase 30.5 filters and H.264 encoder.


echo.
echo [STEP] Restarting Ollama with CrawlMedia model storage
call :resolve_ollama
if errorlevel 1 goto :fail
call :restart_ollama_server
if errorlevel 1 goto :fail
call :ollama_pull "%WRITER_MODEL%"
if errorlevel 1 goto :fail
call :ollama_pull "%VERIFIER_MODEL%"
if errorlevel 1 goto :fail


echo.
echo [STEP] Installing/updating ComfyUI
if exist "%COMFY_HOME%\.git" (
    git -C "%COMFY_HOME%" pull --ff-only
    if errorlevel 1 (
        echo [ERROR] Existing ComfyUI checkout could not fast-forward.
        echo Resolve local ComfyUI changes manually, then rerun this installer.
        goto :fail
    )
) else (
    if exist "%COMFY_HOME%" (
        echo [ERROR] "%COMFY_HOME%" exists but is not a Git checkout.
        echo Move/remove that directory or set UNDERREACH_MEDIA_HOME to another location.
        goto :fail
    )
    git clone --depth 1 https://github.com/Comfy-Org/ComfyUI.git "%COMFY_HOME%"
    if errorlevel 1 goto :fail
)

if not exist "%COMFY_HOME%\.venv\Scripts\python.exe" (
    "%PY312%" -m venv "%COMFY_HOME%\.venv"
    if errorlevel 1 goto :fail
)
set "COMFY_PY=%COMFY_HOME%\.venv\Scripts\python.exe"
"%COMFY_PY%" -m pip install --upgrade pip setuptools wheel
if errorlevel 1 goto :fail

call :install_cuda_torch
if errorlevel 1 goto :fail

"%COMFY_PY%" -m pip install -r "%COMFY_HOME%\requirements.txt"
if errorlevel 1 goto :fail
"%COMFY_PY%" -m pip check
if errorlevel 1 goto :fail
"%COMFY_PY%" -c "import torch,sys; print('PyTorch',torch.__version__,'CUDA runtime',torch.version.cuda,'CUDA available',torch.cuda.is_available()); sys.exit(0 if torch.cuda.is_available() else 2)"
if errorlevel 1 (
    echo [ERROR] ComfyUI PyTorch cannot see the NVIDIA GPU after dependency install.
    goto :fail
)

if not exist "%COMFY_HOME%\models\checkpoints" mkdir "%COMFY_HOME%\models\checkpoints"
if not exist "%COMFY_HOME%\models\diffusion_models" mkdir "%COMFY_HOME%\models\diffusion_models"
if not exist "%COMFY_HOME%\models\text_encoders" mkdir "%COMFY_HOME%\models\text_encoders"
if not exist "%COMFY_HOME%\models\vae" mkdir "%COMFY_HOME%\models\vae"
if not exist "%KOKORO_HOME%" mkdir "%KOKORO_HOME%"
if not exist "%WORKFLOW_HOME%" mkdir "%WORKFLOW_HOME%"
if not exist "%AUDIO_HOME%\music" mkdir "%AUDIO_HOME%\music"
if not exist "%AUDIO_HOME%\sfx" mkdir "%AUDIO_HOME%\sfx"
if not exist "%OUTPUT_HOME%" mkdir "%OUTPUT_HOME%"


echo.
echo [STEP] Pulling SDXL Base 1.0 for local image production
call :ensure_hf_file ^
  "stabilityai/stable-diffusion-xl-base-1.0" ^
  "sd_xl_base_1.0.safetensors" ^
  "%COMFY_HOME%\models\checkpoints\sd_xl_base_1.0.safetensors" ^
  "31e35c80fc4829d14f90153f4c74cd59c90b779f6afe05a74cd6120b893f7e5b"
if errorlevel 1 goto :fail


echo.
echo [STEP] Pulling Wan 2.2 TI2V 5B for optional local image-to-video
call :ensure_hf_file ^
  "Comfy-Org/Wan_2.2_ComfyUI_Repackaged" ^
  "split_files/diffusion_models/wan2.2_ti2v_5B_fp16.safetensors" ^
  "%COMFY_HOME%\models\diffusion_models\wan2.2_ti2v_5B_fp16.safetensors" ^
  "456f901338bd9eadbded3828b819109a9b68e8a525ca5cf8d0049a69fcfeca1e"
if errorlevel 1 goto :fail
call :ensure_hf_file ^
  "Comfy-Org/Wan_2.2_ComfyUI_Repackaged" ^
  "split_files/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors" ^
  "%COMFY_HOME%\models\text_encoders\umt5_xxl_fp8_e4m3fn_scaled.safetensors" ^
  "c3355d30191f1f066b26d93fba017ae9809dce6c627dda5f6a66eaa651204f68"
if errorlevel 1 goto :fail
call :ensure_hf_file ^
  "Comfy-Org/Wan_2.2_ComfyUI_Repackaged" ^
  "split_files/vae/wan2.2_vae.safetensors" ^
  "%COMFY_HOME%\models\vae\wan2.2_vae.safetensors" ^
  "e40321bd36b9709991dae2530eb4ac303dd168276980d3e9bc4b6e2b75fed156"
if errorlevel 1 goto :fail


echo.
echo [STEP] Pulling Kokoro-82M v1.0 model and voices
call :ensure_kokoro
if errorlevel 1 goto :fail


echo.
echo [STEP] Downloading official ComfyUI workflow templates
call :download_small ^
  "https://raw.githubusercontent.com/Comfy-Org/workflow_templates/refs/heads/main/templates/sdxl_simple_example.json" ^
  "%WORKFLOW_HOME%\sdxl_simple_example.json"
if errorlevel 1 goto :fail
call :download_small ^
  "https://raw.githubusercontent.com/Comfy-Org/workflow_templates/refs/heads/main/templates/video_wan2_2_5B_ti2v.json" ^
  "%WORKFLOW_HOME%\video_wan2_2_5B_ti2v.json"
if errorlevel 1 goto :fail


echo.
echo [STEP] Writing local service launchers and installation manifest
> "%MEDIA_HOME%\start-ollama-underreach.bat" echo @echo off
>> "%MEDIA_HOME%\start-ollama-underreach.bat" echo set "OLLAMA_MODELS=%OLLAMA_MODEL_HOME%"
>> "%MEDIA_HOME%\start-ollama-underreach.bat" echo "%OLLAMA_EXE%" serve

> "%MEDIA_HOME%\start-comfyui-underreach.bat" echo @echo off
>> "%MEDIA_HOME%\start-comfyui-underreach.bat" echo cd /d "%COMFY_HOME%"
>> "%MEDIA_HOME%\start-comfyui-underreach.bat" echo "%COMFY_HOME%\.venv\Scripts\python.exe" main.py --listen 127.0.0.1 --port 8188 --lowvram

> "%MEDIA_HOME%\start-underreach-media-services.bat" echo @echo off
>> "%MEDIA_HOME%\start-underreach-media-services.bat" echo start "Underreach Ollama" "%MEDIA_HOME%\start-ollama-underreach.bat"
>> "%MEDIA_HOME%\start-underreach-media-services.bat" echo timeout /t 3 /nobreak ^>nul
>> "%MEDIA_HOME%\start-underreach-media-services.bat" echo start "Underreach ComfyUI" "%MEDIA_HOME%\start-comfyui-underreach.bat"

> "%MEDIA_HOME%\underreach-media.env" echo UNDERREACH_MEDIA_HOME=%MEDIA_HOME%
>> "%MEDIA_HOME%\underreach-media.env" echo OLLAMA_MODELS=%OLLAMA_MODEL_HOME%
>> "%MEDIA_HOME%\underreach-media.env" echo OLLAMA_BASE_URL=http://127.0.0.1:11434
>> "%MEDIA_HOME%\underreach-media.env" echo UNDERREACH_WRITER_MODEL=%WRITER_MODEL%
>> "%MEDIA_HOME%\underreach-media.env" echo UNDERREACH_VERIFIER_MODEL=%VERIFIER_MODEL%
>> "%MEDIA_HOME%\underreach-media.env" echo COMFYUI_BASE_URL=http://127.0.0.1:8188
>> "%MEDIA_HOME%\underreach-media.env" echo UNDERREACH_SDXL_CHECKPOINT=sd_xl_base_1.0.safetensors
>> "%MEDIA_HOME%\underreach-media.env" echo UNDERREACH_WAN_MODEL=wan2.2_ti2v_5B_fp16.safetensors
>> "%MEDIA_HOME%\underreach-media.env" echo UNDERREACH_KOKORO_HOME=%KOKORO_HOME%
>> "%MEDIA_HOME%\underreach-media.env" echo UNDERREACH_MUSIC_LIBRARY=%AUDIO_HOME%\music
>> "%MEDIA_HOME%\underreach-media.env" echo UNDERREACH_SFX_LIBRARY=%AUDIO_HOME%\sfx

> "%MEDIA_HOME%\UNDERREACH_MEDIA_INSTALL.txt" echo UNDERREACH MEDIA PIPELINE INSTALL
>> "%MEDIA_HOME%\UNDERREACH_MEDIA_INSTALL.txt" echo Media home=%MEDIA_HOME%
>> "%MEDIA_HOME%\UNDERREACH_MEDIA_INSTALL.txt" echo Crawl venv=%REPO_ROOT%\.venv
>> "%MEDIA_HOME%\UNDERREACH_MEDIA_INSTALL.txt" echo Media Python venv=%MEDIA_VENV%
>> "%MEDIA_HOME%\UNDERREACH_MEDIA_INSTALL.txt" echo ComfyUI=%COMFY_HOME%
>> "%MEDIA_HOME%\UNDERREACH_MEDIA_INSTALL.txt" echo Ollama model home=%OLLAMA_MODEL_HOME%
>> "%MEDIA_HOME%\UNDERREACH_MEDIA_INSTALL.txt" echo Writer model=%WRITER_MODEL%
>> "%MEDIA_HOME%\UNDERREACH_MEDIA_INSTALL.txt" echo Verifier model=%VERIFIER_MODEL%
>> "%MEDIA_HOME%\UNDERREACH_MEDIA_INSTALL.txt" echo SDXL checkpoint=sd_xl_base_1.0.safetensors
>> "%MEDIA_HOME%\UNDERREACH_MEDIA_INSTALL.txt" echo Wan model=wan2.2_ti2v_5B_fp16.safetensors
>> "%MEDIA_HOME%\UNDERREACH_MEDIA_INSTALL.txt" echo Wan text encoder=umt5_xxl_fp8_e4m3fn_scaled.safetensors
>> "%MEDIA_HOME%\UNDERREACH_MEDIA_INSTALL.txt" echo Wan VAE=wan2.2_vae.safetensors
>> "%MEDIA_HOME%\UNDERREACH_MEDIA_INSTALL.txt" echo Kokoro=%KOKORO_HOME%
>> "%MEDIA_HOME%\UNDERREACH_MEDIA_INSTALL.txt" echo ComfyUI URL=http://127.0.0.1:8188
>> "%MEDIA_HOME%\UNDERREACH_MEDIA_INSTALL.txt" echo Ollama URL=http://127.0.0.1:11434
>> "%MEDIA_HOME%\UNDERREACH_MEDIA_INSTALL.txt" echo Music library=%AUDIO_HOME%\music
>> "%MEDIA_HOME%\UNDERREACH_MEDIA_INSTALL.txt" echo SFX library=%AUDIO_HOME%\sfx
>> "%MEDIA_HOME%\UNDERREACH_MEDIA_INSTALL.txt" echo Output=%OUTPUT_HOME%
>> "%MEDIA_HOME%\UNDERREACH_MEDIA_INSTALL.txt" echo Workflow SDXL=%WORKFLOW_HOME%\sdxl_simple_example.json
>> "%MEDIA_HOME%\UNDERREACH_MEDIA_INSTALL.txt" echo Workflow Wan=%WORKFLOW_HOME%\video_wan2_2_5B_ti2v.json


echo.
echo [STEP] Final smoke checks
"%PROJECT_PY%" -c "import livingworld; print('Crawl Python import: OK')"
if errorlevel 1 goto :fail
"%MEDIA_PY%" -c "import kokoro, soundfile, huggingface_hub; print('Kokoro + Hugging Face Python imports: OK')"
if errorlevel 1 goto :fail
call :hash_ok "%COMFY_HOME%\models\checkpoints\sd_xl_base_1.0.safetensors" "31e35c80fc4829d14f90153f4c74cd59c90b779f6afe05a74cd6120b893f7e5b"
if errorlevel 1 goto :fail
call :hash_ok "%COMFY_HOME%\models\diffusion_models\wan2.2_ti2v_5B_fp16.safetensors" "456f901338bd9eadbded3828b819109a9b68e8a525ca5cf8d0049a69fcfeca1e"
if errorlevel 1 goto :fail
call :hash_ok "%COMFY_HOME%\models\text_encoders\umt5_xxl_fp8_e4m3fn_scaled.safetensors" "c3355d30191f1f066b26d93fba017ae9809dce6c627dda5f6a66eaa651204f68"
if errorlevel 1 goto :fail
call :hash_ok "%COMFY_HOME%\models\vae\wan2.2_vae.safetensors" "e40321bd36b9709991dae2530eb4ac303dd168276980d3e9bc4b6e2b75fed156"
if errorlevel 1 goto :fail
call :hash_ok "%KOKORO_HOME%\kokoro-v1_0.pth" "496dba118d1a58f5f3db2efc88dbdc216e0483fc89fe6e47ee1f2c53f18ad1e4"
if errorlevel 1 goto :fail
"%OLLAMA_EXE%" show "%WRITER_MODEL%" >nul 2>&1
if errorlevel 1 goto :fail
"%OLLAMA_EXE%" show "%VERIFIER_MODEL%" >nul 2>&1
if errorlevel 1 goto :fail

if exist "%HF_CACHE%" (
    echo [CLEANUP] Removing completed Hugging Face download cache...
    rmdir /s /q "%HF_CACHE%" >nul 2>&1
)
if exist "%HF_STAGE%" rmdir /s /q "%HF_STAGE%" >nul 2>&1


echo.
echo ============================================================
echo  INSTALL COMPLETE
echo ============================================================
echo Writer:     %WRITER_MODEL%
echo Verifier:   %VERIFIER_MODEL%
echo Image:      SDXL Base 1.0
echo Video:      Wan 2.2 TI2V 5B
echo Voice:      Kokoro-82M v1.0
echo Editor:     FFmpeg
echo ComfyUI:    %COMFY_HOME%
echo Media home: %MEDIA_HOME%
echo.
echo Start all local AI/media services with:
echo   "%MEDIA_HOME%\start-underreach-media-services.bat"
echo.
echo Crawl project virtual environment:
echo   "%REPO_ROOT%\.venv"
echo.
echo Dedicated media Python environment:
echo   "%MEDIA_VENV%"
echo.
echo Royalty-safe music and SFX can be added to:
echo   "%AUDIO_HOME%\music"
echo   "%AUDIO_HOME%\sfx"
echo.
echo No cloud or paid provider was configured.
exit /b 0


:check_disk
set "DISK_PATH=%~1"
set "REQUIRED_GB=%~2"
set "FREE_GB="
for /f "usebackq delims=" %%G in (`powershell -NoProfile -Command "$root=[IO.Path]::GetPathRoot($env:DISK_PATH); $drive=$root.Substring(0,1); [math]::Floor((Get-PSDrive -Name $drive).Free/1GB)"`) do set "FREE_GB=%%G"
if not defined FREE_GB (
    echo [WARN] Could not determine free disk space. Continuing.
    exit /b 0
)
echo [INFO] Free space on media drive: !FREE_GB! GB
if !FREE_GB! LSS %REQUIRED_GB% (
    echo [ERROR] At least %REQUIRED_GB% GB free is required for the full local media stack.
    exit /b 1
)
exit /b 0


:winget_install
set "PKG_ID=%~1"
set "PKG_NAME=%~2"
winget list --id "%PKG_ID%" -e 2>nul | findstr /I /C:"%PKG_ID%" >nul
if not errorlevel 1 (
    echo [OK] %PKG_NAME% already installed.
    exit /b 0
)
echo [INSTALL] %PKG_NAME%...
winget install --id "%PKG_ID%" -e --accept-package-agreements --accept-source-agreements --silent --disable-interactivity
if errorlevel 1 (
    echo [ERROR] WinGet failed to install %PKG_NAME% ^(%PKG_ID%^).
    exit /b 1
)
exit /b 0


:ensure_user_path
set "ADD_PATH=%~1"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$add=$env:ADD_PATH; $p=[Environment]::GetEnvironmentVariable('Path','User'); if([string]::IsNullOrWhiteSpace($p)){$p=''}; if(-not (($p -split ';') -contains $add)){[Environment]::SetEnvironmentVariable('Path',(($p.TrimEnd(';')+';'+$add).Trim(';')),'User')}"
exit /b 0


:set_user_env
set "ENV_NAME=%~1"
set "ENV_VALUE=%~2"
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Environment]::SetEnvironmentVariable($env:ENV_NAME,$env:ENV_VALUE,'User')"
exit /b 0


:resolve_python312
set "PY312="
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PY312=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PY312 if exist "%ProgramFiles%\Python312\python.exe" set "PY312=%ProgramFiles%\Python312\python.exe"
if not defined PY312 (
    for /f "usebackq delims=" %%P in (`py -3.12 -c "import sys; print(sys.executable)" 2^>nul`) do set "PY312=%%P"
)
if not defined PY312 (
    echo [ERROR] Python 3.12 was installed but its interpreter could not be located.
    exit /b 1
)
"%PY312%" -c "import sys; print('Python', sys.version)"
if errorlevel 1 exit /b 1
exit /b 0


:verify_node20
where node >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js was installed but node.exe is not visible on PATH.
    exit /b 1
)
where npm >nul 2>&1
if errorlevel 1 (
    echo [ERROR] npm was not found.
    exit /b 1
)
node -e "const m=Number(process.versions.node.split('.')[0]); console.log('Node',process.versions.node); process.exit(m>=20?0:2)"
if errorlevel 1 (
    echo [ERROR] Crawl requires Node.js 20 or newer.
    exit /b 1
)
exit /b 0


:check_nvidia
set "NVIDIA_SMI="
where nvidia-smi >nul 2>&1
if not errorlevel 1 set "NVIDIA_SMI=nvidia-smi"
if not defined NVIDIA_SMI if exist "%ProgramFiles%\NVIDIA Corporation\NVSMI\nvidia-smi.exe" set "NVIDIA_SMI=%ProgramFiles%\NVIDIA Corporation\NVSMI\nvidia-smi.exe"
if not defined NVIDIA_SMI (
    echo [ERROR] NVIDIA driver tools were not found.
    echo Install/update the NVIDIA driver for the RTX GPU, reboot if requested, then rerun this installer.
    exit /b 1
)
"%NVIDIA_SMI%" --query-gpu=name,driver_version,memory.total --format=csv,noheader
if errorlevel 1 (
    echo [ERROR] NVIDIA driver is installed but nvidia-smi could not query the GPU.
    exit /b 1
)
exit /b 0


:resolve_ollama
set "OLLAMA_EXE="
where ollama >nul 2>&1
if not errorlevel 1 set "OLLAMA_EXE=ollama"
if not defined OLLAMA_EXE if exist "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" set "OLLAMA_EXE=%LOCALAPPDATA%\Programs\Ollama\ollama.exe"
if not defined OLLAMA_EXE (
    echo [ERROR] Ollama was installed but ollama.exe could not be located.
    exit /b 1
)
exit /b 0


:restart_ollama_server
echo [INFO] Stopping any existing Ollama process so OLLAMA_MODELS takes effect...
taskkill /IM ollama.exe /F >nul 2>&1
taskkill /IM "ollama app.exe" /F >nul 2>&1
timeout /t 2 /nobreak >nul
start "Underreach Ollama" /min "%OLLAMA_EXE%" serve
timeout /t 6 /nobreak >nul
"%OLLAMA_EXE%" list >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Ollama server did not become available on http://127.0.0.1:11434.
    exit /b 1
)
exit /b 0


:ollama_pull
set "OLLAMA_MODEL=%~1"
"%OLLAMA_EXE%" show "%OLLAMA_MODEL%" >nul 2>&1
if not errorlevel 1 (
    echo [OK] Ollama model %OLLAMA_MODEL% already present.
    exit /b 0
)
echo [DOWNLOAD] Ollama model %OLLAMA_MODEL%...
"%OLLAMA_EXE%" pull "%OLLAMA_MODEL%"
if errorlevel 1 (
    echo [ERROR] Failed to pull Ollama model %OLLAMA_MODEL%.
    exit /b 1
)
exit /b 0


:install_cuda_torch
echo [STEP] Installing PyTorch 2.11 CUDA 13.0 for ComfyUI
"%COMFY_PY%" -m pip install --upgrade torch==2.11.0 torchvision==0.26.0 torchaudio==2.11.0 --index-url https://download.pytorch.org/whl/cu130
if not errorlevel 1 (
    "%COMFY_PY%" -c "import torch,sys; print('CUDA 13 PyTorch GPU check:',torch.cuda.is_available()); sys.exit(0 if torch.cuda.is_available() else 2)"
    if not errorlevel 1 exit /b 0
)
echo [WARN] CUDA 13.0 wheel/driver path failed. Trying CUDA 12.8.
"%COMFY_PY%" -m pip uninstall -y torch torchvision torchaudio >nul 2>&1
"%COMFY_PY%" -m pip install torch==2.11.0 torchvision==0.26.0 torchaudio==2.11.0 --index-url https://download.pytorch.org/whl/cu128
if errorlevel 1 (
    echo [ERROR] Could not install CUDA-enabled PyTorch for ComfyUI.
    exit /b 1
)
"%COMFY_PY%" -c "import torch,sys; print('CUDA 12.8 PyTorch GPU check:',torch.cuda.is_available()); sys.exit(0 if torch.cuda.is_available() else 2)"
if errorlevel 1 (
    echo [ERROR] PyTorch cannot see the NVIDIA GPU. Update the NVIDIA driver and rerun.
    exit /b 1
)
exit /b 0


:ensure_hf_file
set "HF_REPO=%~1"
set "HF_REMOTE=%~2"
set "HF_DEST=%~3"
set "HF_SHA=%~4"

if exist "%HF_DEST%" (
    call :hash_ok "%HF_DEST%" "%HF_SHA%"
    if not errorlevel 1 (
        echo [OK] %HF_DEST%
        exit /b 0
    )
    echo [WARN] Existing file failed SHA-256 verification and will be replaced:
    echo        %HF_DEST%
    del /f /q "%HF_DEST%" >nul 2>&1
)

for %%D in ("%HF_DEST%") do if not exist "%%~dpD" mkdir "%%~dpD"
if not exist "%HF_STAGE%" mkdir "%HF_STAGE%"

echo [DOWNLOAD] %HF_REPO% :: %HF_REMOTE%
"%HF_EXE%" download "%HF_REPO%" "%HF_REMOTE%" --local-dir "%HF_STAGE%"
if errorlevel 1 (
    echo [ERROR] Hugging Face download failed. Partial cache files were kept for resume.
    echo If the repository requires authentication, set HF_TOKEN and rerun.
    exit /b 1
)

set "HF_LOCAL_REL=%HF_REMOTE:/=\%"
set "HF_STAGED=%HF_STAGE%\!HF_LOCAL_REL!"
if not exist "!HF_STAGED!" (
    echo [ERROR] Hugging Face CLI completed but the expected staged file was not found:
    echo        !HF_STAGED!
    exit /b 1
)
move /Y "!HF_STAGED!" "%HF_DEST%" >nul
if errorlevel 1 exit /b 1

call :hash_ok "%HF_DEST%" "%HF_SHA%"
if errorlevel 1 (
    echo [ERROR] SHA-256 verification failed after download:
    echo        %HF_DEST%
    exit /b 1
)
rmdir /s /q "%HF_STAGE%" >nul 2>&1
echo [OK] Verified %HF_DEST%
exit /b 0


:ensure_kokoro
if exist "%KOKORO_HOME%\kokoro-v1_0.pth" if exist "%KOKORO_HOME%\voices" (
    call :hash_ok "%KOKORO_HOME%\kokoro-v1_0.pth" "496dba118d1a58f5f3db2efc88dbdc216e0483fc89fe6e47ee1f2c53f18ad1e4"
    if not errorlevel 1 (
        echo [OK] Kokoro model and voices already present.
        exit /b 0
    )
)
echo [DOWNLOAD] hexgrad/Kokoro-82M model + voices...
"%HF_EXE%" download "hexgrad/Kokoro-82M" --local-dir "%KOKORO_HOME%"
if errorlevel 1 (
    echo [ERROR] Kokoro model download failed.
    exit /b 1
)
call :hash_ok "%KOKORO_HOME%\kokoro-v1_0.pth" "496dba118d1a58f5f3db2efc88dbdc216e0483fc89fe6e47ee1f2c53f18ad1e4"
if errorlevel 1 (
    echo [ERROR] Kokoro core weight failed SHA-256 verification.
    exit /b 1
)
if not exist "%KOKORO_HOME%\voices" (
    echo [ERROR] Kokoro voices directory is missing after download.
    exit /b 1
)
echo [OK] Kokoro model and voices verified.
exit /b 0


:download_small
set "DL_URL=%~1"
set "DL_DEST=%~2"
if exist "%DL_DEST%" (
    echo [OK] %DL_DEST%
    exit /b 0
)
for %%D in ("%DL_DEST%") do if not exist "%%~dpD" mkdir "%%~dpD"
curl.exe -L --fail --retry 5 --retry-delay 2 -o "%DL_DEST%" "%DL_URL%"
if errorlevel 1 (
    echo [ERROR] Failed to download %DL_URL%
    exit /b 1
)
exit /b 0


:hash_ok
set "HASH_FILE=%~1"
set "HASH_EXPECTED=%~2"
if not exist "%HASH_FILE%" exit /b 1
set "HASH_ACTUAL="
for /f "usebackq delims=" %%H in (`powershell -NoProfile -Command "(Get-FileHash -Algorithm SHA256 -LiteralPath $env:HASH_FILE).Hash.ToLowerInvariant()"`) do set "HASH_ACTUAL=%%H"
if /I "!HASH_ACTUAL!"=="%HASH_EXPECTED%" exit /b 0
exit /b 1


:fail
echo.
echo ============================================================
echo  INSTALL FAILED
echo ============================================================
echo The installer is safe to rerun. Completed installs and verified models are kept.
echo Interrupted Hugging Face cache data is kept under:
echo   %HF_CACHE%
echo Fix the reported error and rerun this same batch file.
exit /b 1
