@echo off
echo ==========================================================
echo           GMIS WebApp - Backend Server (FastAPI)
echo ==========================================================
echo.

:: 1. 백엔드 전용 Python 가상환경 활성화
echo Activating Python virtual environment...
call packages\backend\venv\Scripts\activate.bat

:: 2. 백엔드 폴더로 이동
echo Changing directory to backend...
cd packages\backend

:: 3. FastAPI 개발 서버 실행 (Uvicorn)
echo Starting Uvicorn server for main_api:app...
echo Visit http://localhost:8000 in your browser.
echo.
uvicorn main_api:app --reload --host 0.0.0.0 --port 8000

:: 서버 종료 시 원래 폴더로 복귀 (선택 사항)
cd ..\..

pause

