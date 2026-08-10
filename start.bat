@echo off
REM Track the Date - Tecoma
REM Double-click this to bring the app up. Close the window to stop it.

cd /d "%~dp0"
title Track the Date - Tecoma

if not exist "data\tecoma.db" (
    echo No database found. Creating one...
    python scripts\init_db.py
    echo.
    echo Now import the old data with:
    echo    python scripts\import_beep.py data\imports\beep_2026-08-10.xlsx
    echo.
    pause
    exit /b
)

REM Back up on startup rather than overnight. The laptop is not on overnight,
REM so a scheduled 2am backup would never run.
python scripts\backup.py --quiet

REM Use HTTPS if certificates exist, plain HTTP otherwise. iPad camera
REM scanning needs HTTPS; everything else works either way.
REM To create them:  mkcert -key-file certs\key.pem -cert-file certs\cert.pem <this-machine-ip>
set SSL=
set SCHEME=http
set PORT=8000
if exist "certs\cert.pem" if exist "certs\key.pem" (
    set SSL=--ssl-certfile certs\cert.pem --ssl-keyfile certs\key.pem
    set SCHEME=https
    set PORT=8443
)

echo.
echo   ======================================================
echo     Track the Date - Tecoma
echo   ======================================================
python scripts\show_address.py %SCHEME% %PORT%
echo   Leave this window open while staff are using the app.
echo   Closing it, or pressing Ctrl+C, stops the app.
echo.
echo   Anything already saved is safe. It is on the disk.
echo   ======================================================
echo.

python -m uvicorn app.main:app --host 0.0.0.0 --port %PORT% %SSL%

echo.
echo   App stopped. All saved data is on the disk.
pause
