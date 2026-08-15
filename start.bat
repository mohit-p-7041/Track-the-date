@echo off
REM ====================================================================
REM  Track the Date - Tecoma
REM
REM  Double-click this to start the app. Close the window to stop it.
REM  Nothing else needs doing; everything staff save is written to disk
REM  as they go.
REM
REM  This file only finds Python. Every decision - which port, http or
REM  https, whether it is already running - is in scripts\serve.py,
REM  because batch is a bad language for decisions and cannot be tested.
REM
REM  Plain ASCII on purpose: a Windows console renders anything else as
REM  rubbish depending on the code page.
REM ====================================================================

cd /d "%~dp0"
title Track the Date - Tecoma

REM The py launcher first. It ships with the python.org installer and keeps
REM working when PATH does not, which is the usual Windows breakage. Both
REM are tested by actually running them: "python" on a machine where it was
REM never installed is a Microsoft Store stub that exists, prints an advert
REM and exits, and "where python" cannot tell the difference.
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
    echo   on the first screen of the installer. Then run setup.bat once,
    echo   and after that this file.
    echo.
    echo   The full steps are in docs\WINDOWS-SETUP.md.
    echo.
    pause
    exit /b 1
)

%PY% scripts\serve.py %*

echo.
echo   The app has stopped. Everything staff saved is on the disk.
echo   You can close this window.
echo.
pause >nul
