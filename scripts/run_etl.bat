@echo off
setlocal
chcp 65001 > nul

echo ======================================================================
echo   GMIS Knowledge Graph ETL Pipeline v5 Runner
echo ======================================================================
echo.

set "VENV_DIR=venv"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"
set "SCRIPT=gmisknowledgegraphetl_v5_final.py"
set "LOG_FILE=etl_v5_log_%date:~0,4%%date:~5,2%%date:~8,2%_%time:~0,2%%time:~3,2%%time:~6,2%.txt"

echo [1/2] 가상환경 확인 중...
if not exist "%VENV_PYTHON%" (
    echo [ERROR] 가상환경을 찾을 수 없습니다.
    echo run_etl.bat를 먼저 실행하여 가상환경을 생성하세요.
    pause
    exit /b 1
)
echo   - 완료: 가상환경이 준비되었습니다.

echo.
echo [2/2] ETL v5 실행 중... (로그: %LOG_FILE%)
echo ======================================================================
echo.

"%VENV_PYTHON%" "%SCRIPT%" > "%LOG_FILE%" 2>&1

echo.
echo 로그를 화면에 출력합니다...
echo.
type "%LOG_FILE%"

echo.
echo ======================================================================
echo 실행이 완료되었습니다.
echo 로그 파일: %LOG_FILE%
echo.

pause

