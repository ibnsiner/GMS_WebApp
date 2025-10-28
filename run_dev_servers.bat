@echo off
echo ==========================================================
echo      GMIS WebApp - Starting All Development Servers
echo ==========================================================
echo.
echo Starting Backend and Frontend servers in separate windows...
echo.

:: "Backend Server"라는 제목의 새 창에서 run_backend.bat 실행
start "Backend Server" cmd /c run_backend.bat

:: "Frontend Server"라는 제목의 새 창에서 run_frontend.bat 실행
start "Frontend Server" cmd /c run_frontend.bat

echo.
echo Both servers are starting up.
echo Backend: http://localhost:8000
echo Frontend: http://localhost:3000
echo.
echo Press any key to close this window...
pause > nul

