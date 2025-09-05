@echo off
setlocal enabledelayedexpansion
set ROOT=%~dp0
set BACKEND_DIR=%ROOT%app\backend
set FRONTEND_DIR=%ROOT%app\frontend
set LOG_DIR=%ROOT%logs

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

rem helper to log to console and file
:_init
if not defined LOG_FILE set "LOG_FILE=%LOG_DIR%\start.log"
goto :eof

:log
echo [%date% %time%] %~1
echo [%date% %time%] %~1>>"%LOG_FILE%"
goto :eof

call :_init

rem ---------------------------------------------------------------------------
rem  Start script
rem ---------------------------------------------------------------------------

call :log "Starting setup"

rem touch individual logs so user can open them immediately
type nul > "%LOG_DIR%\backend.log"
type nul > "%LOG_DIR%\frontend.log"

call :log "Backend setup..."
if not exist "%BACKEND_DIR%\.venv\Scripts\python.exe" (
  pushd "%BACKEND_DIR%"
  python -m venv .venv >> "%LOG_DIR%\backend.log" 2>&1
  popd
)
pushd "%BACKEND_DIR%"
"%BACKEND_DIR%\.venv\Scripts\python.exe" -m pip install -U pip >> "%LOG_DIR%\backend.log" 2>&1
"%BACKEND_DIR%\.venv\Scripts\python.exe" -m pip install -r requirements.txt >> "%LOG_DIR%\backend.log" 2>&1
popd
start "backend" cmd /c "cd /d \"%BACKEND_DIR%\" && \"%BACKEND_DIR%\\.venv\\Scripts\\python.exe\" -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload 1>>\"%LOG_DIR%\\backend.log\" 2>&1"
call :log "Backend starting on http://localhost:8000"

call :log "Frontend setup..."
pushd "%FRONTEND_DIR%"
npm install >> "%LOG_DIR%\frontend.log" 2>&1
popd
start "frontend" cmd /k "cd /d \"%FRONTEND_DIR%\" && npm run dev 1>>\"%LOG_DIR%\\frontend.log\" 2>&1"
call :log "Frontend starting on http://localhost:5173"

rem give Vite a moment, then open browser
timeout /t 5 > nul
start "" "http://localhost:5173"

call :log "Done. Logs available in %LOG_DIR%"
exit /b 0
