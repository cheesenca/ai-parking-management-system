@echo off
setlocal

echo ============================================
echo   AIPS - Starting full stack
echo ============================================
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
