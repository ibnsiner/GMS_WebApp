@echo off
echo ==========================================================
echo          GMIS WebApp - Frontend Server (Next.js)
echo ==========================================================
echo.

:: 1. 프론트엔드 폴더로 이동
echo Changing directory to frontend...
cd packages\frontend

:: 2. Next.js 개발 서버 실행 (npm)
echo Starting Next.js development server...
echo Visit http://localhost:3000 in your browser.
echo.
npm run dev

:: 서버 종료 시 원래 폴더로 복귀 (선택 사항)
cd ..\..

pause

