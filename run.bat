@echo off
REM ==========================================================================
REM  One-command launcher for Windows.
REM    run.bat            -> set up (first time) and process the config's input folder
REM    run.bat gui        -> launch the offline GUI
REM    run.bat streams f  -> list streams in file f
REM    run.bat <args...>  -> forwarded to xon-pipeline
REM  Creates a self-contained .venv the first time; no global installs, no git needed.
REM ==========================================================================
setlocal
cd /d "%~dp0"

REM --- auto-update the CODE from GitHub (your data/outputs/.venv are untouched; only the
REM --- public code is fetched, so it stays HIPAA-safe). Set XON_NO_UPDATE=1 to freeze.
if not "%XON_NO_UPDATE%"=="1" (
  powershell -NoProfile -ExecutionPolicy Bypass -Command ^
   "try { $r='Harshu-Pande/xon-aperiodic-pipeline'; $h=@{'User-Agent'='xon'}; $latest=(Invoke-RestMethod -TimeoutSec 8 -Headers $h -Uri ('https://api.github.com/repos/'+$r+'/commits/main')).sha; $cur=''; if(Test-Path '.xon_version'){$cur=Get-Content '.xon_version'}; if($latest -and -not $cur){Set-Content '.xon_version' $latest} elseif($latest -and $latest -ne $cur){ Write-Host 'Updating to the latest version...'; $t=Join-Path $env:TEMP ('xon_'+[guid]::NewGuid()); New-Item -ItemType Directory $t | Out-Null; Invoke-WebRequest -TimeoutSec 90 -Uri ('https://github.com/'+$r+'/archive/refs/heads/main.zip') -OutFile ($t+'\u.zip'); Expand-Archive -Force ($t+'\u.zip') $t; robocopy (Join-Path $t 'xon-aperiodic-pipeline-main') . /E /XD .venv data outputs .git /XF .xon_version run.bat 'Start Here (Windows).bat' | Out-Null; Set-Content '.xon_version' $latest; Remove-Item -Recurse -Force $t } } catch {}"
)

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.9+ from https://www.python.org/downloads/ and re-run.
  exit /b 1
)

if not exist ".venv" (
  echo First run: setting up ^(this happens once^)...
  python -m venv --system-site-packages .venv
  call .venv\Scripts\activate.bat
  python -m pip install --upgrade pip >nul 2>nul
  echo Installing the pipeline ^(only what's missing^)...
  REM Dependencies only; the code runs straight from src\ via PYTHONPATH (more reliable).
  python -m pip install -r requirements.txt >nul
) else (
  call .venv\Scripts\activate.bat
)

REM Optional drag-and-drop support for the desktop GUI (tiny). GUI works without it too.
if "%~1"=="gui" (
  python -c "import tkinterdnd2" 2>nul || python -m pip install tkinterdnd2 >nul 2>nul
)

REM One-double-click Desktop launcher so opening it again later is trivial.
if not exist "%USERPROFILE%\Desktop\Open Xon Pipeline.bat" (
  > "%USERPROFILE%\Desktop\Open Xon Pipeline.bat" echo @echo off
  >> "%USERPROFILE%\Desktop\Open Xon Pipeline.bat" echo cd /d "%CD%"
  >> "%USERPROFILE%\Desktop\Open Xon Pipeline.bat" echo call run.bat gui
  echo Tip: a shortcut 'Open Xon Pipeline' was placed on your Desktop - double-click it next time.
)

set "PYTHONPATH=%CD%\src;%PYTHONPATH%"
if "%~1"=="" (
  python -m xon_aperiodic.cli run
) else (
  python -m xon_aperiodic.cli %*
)
endlocal
