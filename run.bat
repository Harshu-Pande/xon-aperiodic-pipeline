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

if not exist ".venv" (
  echo First run: creating a virtual environment in .venv ^(this happens once^)...
  python -m venv .venv
  call .venv\Scripts\activate.bat
  python -m pip install --upgrade pip >nul
  echo Installing the pipeline and its dependencies...
  python -m pip install -e . >nul
) else (
  call .venv\Scripts\activate.bat
)

REM The GUI needs streamlit (optional extra); install on first use so run.bat gui just works.
if "%~1"=="gui" (
  python -c "import streamlit" 2>nul || (
    echo Installing the GUI ^(streamlit^), one time...
    python -m pip install streamlit >nul
  )
)

if "%~1"=="" (
  xon-pipeline run
) else (
  xon-pipeline %*
)
endlocal
