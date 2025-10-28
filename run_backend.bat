@echo off
echo ==========================================================
echo           GMIS WebApp - Backend Server (FastAPI)
echo ==========================================================
echo.

:: 현재 디렉토리 확인
echo Current directory: %CD%
echo.

:: 백엔드 폴더 확인
echo Checking if backend folder exists...
if not exist "packages\backend" (
    echo ERROR: packages\backend folder not found!
    echo Please make sure you're running this from GMS_WebApp root folder.
    pause
    exit /b 1
)

:: 1. 백엔드 전용 Python 가상환경 확인 및 활성화
if not exist "packages\backend\venv\Scripts\activate.bat" (
    echo WARNING: Virtual environment not found!
    echo Creating virtual environment...
    cd packages\backend
    python -m venv venv
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment!
        echo Please make sure Python is installed and in PATH.
        cd ..\..
        pause
        exit /b 1
    )
    echo Installing dependencies...
    call venv\Scripts\activate.bat
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies!
        cd ..\..
        pause
        exit /b 1
    )
    cd ..\..
)

echo Activating Python virtual environment...
call packages\backend\venv\Scripts\activate.bat

:: 2. 백엔드 폴더로 이동
echo Changing directory to backend...
cd packages\backend
echo Current directory: %CD%
echo.

:: 3. FastAPI 개발 서버 실행 (Uvicorn)
echo Starting Uvicorn server for main_api:app...
echo Visit http://localhost:8000 in your browser.
echo.
echo Press Ctrl+C to stop the server.
echo.

uvicorn main_api:app --reload --host 0.0.0.0 --port 8000

if errorlevel 1 (
    echo.
    echo ERROR: Failed to start Uvicorn server!
    echo Please check the error messages above.
    cd ..\..
    pause
    exit /b 1
)

:: 서버 종료 시 원래 폴더로 복귀
cd ..\..

pause

