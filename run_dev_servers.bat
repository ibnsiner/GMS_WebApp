@echo off
echo ==========================================================
echo      GMIS WebApp - Starting All Development Servers
echo ==========================================================
echo.

:: 현재 디렉토리 확인
echo Current directory: %CD%
echo.

:: 필수 폴더 확인
if not exist "packages\backend" (
    echo ERROR: packages\backend folder not found!
    echo Please make sure you're in the GMS_WebApp root folder.
    pause
    exit /b 1
)

if not exist "packages\frontend" (
    echo ERROR: packages\frontend folder not found!
    echo Please make sure you're in the GMS_WebApp root folder.
    pause
    exit /b 1
)

echo Starting Backend and Frontend servers in separate windows...
echo.

:: "Backend Server"라는 제목의 새 창에서 run_backend.bat 실행
echo [1/2] Launching Backend Server...
start "GMIS Backend (FastAPI)" cmd /k "run_backend.bat"

:: 1초 대기 (백엔드가 먼저 시작되도록)
timeout /t 1 /nobreak > nul

:: "Frontend Server"라는 제목의 새 창에서 run_frontend.bat 실행
echo [2/2] Launching Frontend Server...
start "GMIS Frontend (Next.js)" cmd /k "run_frontend.bat"

echo.
echo =========================================================
echo   Both servers are starting up in separate windows!
echo =========================================================
echo.
echo   Backend Server:   http://localhost:8000
echo   Frontend Server:  http://localhost:3000
echo.
echo   Wait a few seconds for the servers to fully start.
echo   Then open your browser and go to http://localhost:3000
echo.
echo   To stop servers: Close both terminal windows or press Ctrl+C
echo =========================================================
echo.
echo Press any key to close this window...
pause > nul

