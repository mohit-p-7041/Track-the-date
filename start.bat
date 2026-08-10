@echo off
REM Track the Date - Tecoma
REM Development launcher. For the real shop install, run as a service via NSSM.

cd /d "%~dp0"

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

echo Starting Track the Date...
echo.
echo   On this laptop:  http://localhost:8000
echo.
echo   From an iPad, use this machine's address on the shop WiFi.
echo   Run 'ipconfig' in another window to find it.
echo.
echo   Press Ctrl+C to stop.
echo.

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

pause
