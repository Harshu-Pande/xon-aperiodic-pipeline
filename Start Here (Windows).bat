@echo off
REM ==========================================================================
REM  DOUBLE-CLICK THIS FILE to start the Xon pipeline. No terminal needed.
REM  First time: it sets itself up (1-2 min), then opens a page in your browser
REM  where you pick your recordings folder and press one button.
REM ==========================================================================
cd /d "%~dp0"
set "XON_DEFAULT_INPUT=%USERPROFILE%\Downloads\EEG"
set "XON_DEFAULT_OUTPUT=%USERPROFILE%\Desktop\Xon results"
echo ----------------------------------------------------------------
echo   Starting the Xon pipeline.
echo   The FIRST time, setup can take about a minute. Please wait...
echo   An app window will open when it's ready.
echo   (Keep this window open while you use the app.)
echo ----------------------------------------------------------------
echo.
call run.bat gui
pause
