@echo off
setlocal

echo ============================================
echo   AIPS - Starting full stack
echo ============================================
echo.

REM --- Choose which camera features to enable ---
echo  Which features do you want to run?
echo    [1] Full stack  (LPR + Slot Occupancy)
echo    [2] LPR only    (no slot occupancy webcam yet)
echo    [3] Slot Occupancy only  (no LPR webcam yet)
echo.
set "FEATURE_CHOICE="
set /p FEATURE_CHOICE=Choice [1/2/3, default 1]:
if "%FEATURE_CHOICE%"=="2" (
    set NEXT_PUBLIC_ENABLE_LPR=true
    set NEXT_PUBLIC_ENABLE_OCCUPANCY=false
) else if "%FEATURE_CHOICE%"=="3" (
    set NEXT_PUBLIC_ENABLE_LPR=false
    set NEXT_PUBLIC_ENABLE_OCCUPANCY=true
) else (
    set NEXT_PUBLIC_ENABLE_LPR=true
    set NEXT_PUBLIC_ENABLE_OCCUPANCY=true
)
echo.
echo  LPR: %NEXT_PUBLIC_ENABLE_LPR%   Slot Occupancy: %NEXT_PUBLIC_ENABLE_OCCUPANCY%
echo  (The backend and its APIs always start normally - this only turns the
echo   dashboard's camera websockets on/off, so a missing webcam for one
echo   feature won't spam reconnect attempts while you test the other.)
echo.

REM --- Check / start MySQL (XAMPP) ---
netstat -ano | findstr ":3306" >nul
if errorlevel 1 (
    echo [1/3] MySQL not detected on port 3306 - starting XAMPP MySQL...
    if exist "C:\xampp\mysql_start.bat" (
        start "MySQL (XAMPP)" /min "C:\xampp\mysql_start.bat"
        timeout /t 6 /nobreak >nul
    ) else (
        echo   WARNING: C:\xampp\mysql_start.bat not found - start MySQL manually.
    )
) else (
    echo [1/3] MySQL already running on port 3306.
)
echo.

REM --- Start backend (FastAPI/uvicorn) ---
echo [2/3] Starting backend...
start "AIPS Backend" cmd /k "cd /d %~dp0backend && venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload"
echo.

REM --- Start frontend (Next.js) ---
echo [3/3] Starting frontend...
start "AIPS Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"
echo.

echo ============================================
echo   Backend and frontend are starting in
echo   separate windows. Give them a few seconds
echo   (the backend loads ML models on startup).
echo.
echo   Backend health check: http://127.0.0.1:8000/health
echo   Frontend:             http://localhost:3000
echo ============================================
echo.
pause
