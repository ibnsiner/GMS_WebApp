@echo off
echo ==========================================================
echo      GMIS WebApp - Initial Setup (First Time Setup)
echo ==========================================================
echo.
echo This script will:
echo  1. Create Python virtual environment
echo  2. Install all Python dependencies
echo  3. Install all Node.js dependencies
echo.
echo This may take 3-5 minutes. Please be patient.
echo.
pause

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

echo ==========================================================
echo [1/2] Setting up Backend (Python)
echo ==========================================================
echo.

:: 기존 venv가 있으면 삭제
if exist "packages\backend\venv" (
    echo Removing existing virtual environment...
    rmdir /s /q packages\backend\venv
)

echo Creating new Python virtual environment...
cd packages\backend
python -m venv venv
if errorlevel 1 (
    echo ERROR: Failed to create virtual environment!
    echo Please make sure Python is installed and in PATH.
    cd ..\..
    pause
    exit /b 1
)

echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Installing Python dependencies...
pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install Python dependencies!
    cd ..\..
    pause
    exit /b 1
)

echo Backend setup completed!
cd ..\..
echo.

echo ==========================================================
echo [2/2] Setting up Frontend (Node.js)
echo ==========================================================
echo.

:: 기존 node_modules가 있으면 삭제
if exist "packages\frontend\node_modules" (
    echo Removing existing node_modules...
    rmdir /s /q packages\frontend\node_modules
)

if exist "packages\frontend\.next" (
    echo Removing existing .next cache...
    rmdir /s /q packages\frontend\.next
)

echo Installing Node.js dependencies...
cd packages\frontend
call npm install
if errorlevel 1 (
    echo ERROR: Failed to install Node.js dependencies!
    cd ..\..
    pause
    exit /b 1
)

echo Frontend setup completed!
cd ..\..
echo.

echo ==========================================================
echo                    Setup Completed!
echo ==========================================================
echo.
echo   All dependencies have been installed successfully.
echo.
echo   To start development servers, run:
echo   - run_dev_servers.bat (both servers)
echo   - run_backend.bat (backend only)
echo   - run_frontend.bat (frontend only)
echo.
echo ==========================================================
echo.
pause

