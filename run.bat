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

where python >nul 2>nul
if errorlevel 1 (
  echo Python was not found. Install Python 3.9+ from https://www.python.org/downloads/ and re-run.
  exit /b 1
)

REM --- AUTO-UPDATE (smart): pulls the latest code but PRESERVES your local edits
REM --- (config.yaml or src). Handled by update.py. Only public code is fetched; your
REM --- data/outputs/.venv are never touched. Set XON_NO_UPDATE=1 to freeze.
if not "%XON_NO_UPDATE%"=="1" if not "%XON_UPDATED%"=="1" if exist update.py (
  python update.py
  if errorlevel 10 (
    set XON_UPDATED=1
    call run.bat %*
    exit /b
  )
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
