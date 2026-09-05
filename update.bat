@echo off
REM ====================================================================
REM  Track the Date - Tecoma :: update this laptop, then start it
REM
REM  Double-click this to bring the laptop up to the latest version and
REM  start the app in one go. Close the black window when the session
REM  is done, exactly as with the normal icon.
REM
REM  DO NOT right-click and Run as administrator. On this laptop an
REM  elevated window cannot write into the .git folder and the update
REM  dies half way with "Permission denied" - found the hard way on
REM  6 Sep. setup.bat is the one that needs administrator, for the
REM  firewall. This one must not have it, and refuses if it does.
REM
REM  Close the app first if it is already running - this cannot update
REM  code that is in use, and it will say so rather than half-doing it.
REM
REM  Every decision is in scripts\update.py, because batch is a bad
REM  language for decisions and cannot be tested.
REM
REM  Plain ASCII on purpose: a Windows console renders anything else as
REM  rubbish depending on the code page.
REM ====================================================================

cd /d "%~dp0"
title Track the Date - Update

REM The same two-step Python hunt as start.bat and setup.bat, repeated
REM rather than shared: these are the files somebody has to open in
REM eighteen months, and each should make sense on its own.
set "PY="
py -3 -c "pass" >nul 2>&1 && set "PY=py -3"
if not defined PY (
    python -c "pass" >nul 2>&1 && set "PY=python"
)

if not defined PY (
    echo.
    echo   Python is not installed on this laptop, or it is not on PATH.
    echo.
    echo   Install Python from python.org and tick "Add python.exe to PATH"
    echo   on the first screen of the installer. Close this window, open a
    echo   new one, and run setup.bat.
    echo.
    echo   The full steps are in docs\WINDOWS-SETUP.md.
    echo.
    pause
    exit /b 1
)

%PY% scripts\update.py %*

echo.
echo   You can close this window.
echo.
pause >nul
