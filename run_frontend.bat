@echo off
echo ==========================================================
echo          GMIS WebApp - Frontend Server (Next.js)
echo ==========================================================
echo.

:: 현재 디렉토리 확인
echo Current directory: %CD%
echo.

:: 1. 프론트엔드 폴더로 이동
echo Checking if frontend folder exists...
if not exist "packages\frontend" (
    echo ERROR: packages\frontend folder not found!
    echo Please make sure you're running this from GMS_WebApp root folder.
    pause
    exit /b 1
)

echo Changing directory to frontend...
cd packages\frontend
echo Current directory: %CD%
echo.

:: node_modules 확인 및 의존성 설치
if not exist "node_modules" (
    echo node_modules not found. Installing all dependencies...
    call npm install
    if errorlevel 1 (
        echo ERROR: npm install failed!
        cd ..\..
        pause
        exit /b 1
    )
) else (
    echo node_modules found. Checking for missing dependencies...
    call npm install
    if errorlevel 1 (
        echo ERROR: npm install failed!
        cd ..\..
        pause
        exit /b 1
    )
    echo Dependencies verified.
)

:: 2. Next.js 개발 서버 실행 (npm)
echo Starting Next.js development server...
echo Visit http://localhost:3000 in your browser.
echo.
echo Press Ctrl+C to stop the server.
echo.

call npm run dev

if errorlevel 1 (
    echo.
    echo ERROR: Failed to start Next.js development server!
    echo Please check the error messages above.
    cd ..\..
    pause
    exit /b 1
)

:: 서버 종료 시 원래 폴더로 복귀
cd ..\..

pause

