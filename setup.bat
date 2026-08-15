@echo off
REM ====================================================================
REM  Track the Date - Tecoma :: one-time setup
REM
REM  Double-click this ONCE when the laptop is new, or after a git pull
REM  that changed what the app needs. It is safe to run again as often
REM  as you like - every step checks whether it is already done.
REM
REM  Right-click and choose "Run as administrator" to let it open the
REM  Windows firewall for you. Without that it does everything else and
REM  tells you the one thing it skipped.
REM
REM  What it does is listed in scripts\setup_laptop.py, and explained in
REM  docs\WINDOWS-SETUP.md. Plain ASCII on purpose - a Windows console
REM  renders anything else by code page.
REM ====================================================================

cd /d "%~dp0"
title Track the Date - Setup

REM Same two-step Python hunt as start.bat, repeated rather than shared:
REM these two files are the ones somebody has to open in eighteen months
REM and each should make sense on its own.
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
    echo   new one, and run setup.bat again.
    echo.
    echo   The full steps are in docs\WINDOWS-SETUP.md.
    echo.
    pause
    exit /b 1
)

%PY% scripts\setup_laptop.py %*

echo.
pause
