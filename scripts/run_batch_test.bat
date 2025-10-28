@echo off
setlocal
chcp 65001 > nul

rem 프로젝트 루트로 이동
cd /d "%~dp0"

echo ======================================================================
echo   GMIS Agent v4 Batch Test Runner
echo   (Uses agent_v4_batch.py - Original protected)
echo ======================================================================
echo.
echo [Note] This test uses agent_v4_batch.py (not agent_v4_final.py)
echo        to protect the original production version.
echo.

set "VENV_PYTHON=venv\Scripts\python.exe"
set "SCRIPT=test_agent_batch.py"

if not exist "%VENV_PYTHON%" (
    echo [ERROR] Virtual environment not found.
    pause
    exit /b 1
)

echo ======================================================================
echo  Batch Test Options
echo ======================================================================
echo.
echo [Small - 5 tests each]
echo   1. Tests 1-5       2. Tests 6-10      3. Tests 11-15     4. Tests 16-20
echo   5. Tests 21-25     6. Tests 26-30     7. Tests 31-35     8. Tests 36-40
echo   9. Tests 41-45    10. Tests 46-50    11. Tests 51-55    12. Tests 56-60
echo.
echo [Medium - 20 tests each]
echo  21. Group A (1-20)
echo  22. Group B (21-40)
echo  23. Group C (41-60)
echo.
echo [Large]
echo  99. All 60 tests (at once)
echo.
echo [Auto Sequential - Recommended!]
echo  50. Auto: 1-60 in 5-test chunks (safe, with progress tracking)
echo.
echo [Custom]
echo   0. Custom range
echo.
echo ======================================================================
echo.

set /p choice="Select option: "

if "%choice%"=="1" (
    "%VENV_PYTHON%" "%SCRIPT%" 0 5
) else if "%choice%"=="2" (
    "%VENV_PYTHON%" "%SCRIPT%" 5 10
) else if "%choice%"=="3" (
    "%VENV_PYTHON%" "%SCRIPT%" 10 15
) else if "%choice%"=="4" (
    "%VENV_PYTHON%" "%SCRIPT%" 15 20
) else if "%choice%"=="5" (
    "%VENV_PYTHON%" "%SCRIPT%" 20 25
) else if "%choice%"=="6" (
    "%VENV_PYTHON%" "%SCRIPT%" 25 30
) else if "%choice%"=="7" (
    "%VENV_PYTHON%" "%SCRIPT%" 30 35
) else if "%choice%"=="8" (
    "%VENV_PYTHON%" "%SCRIPT%" 35 40
) else if "%choice%"=="9" (
    "%VENV_PYTHON%" "%SCRIPT%" 40 45
) else if "%choice%"=="10" (
    "%VENV_PYTHON%" "%SCRIPT%" 45 50
) else if "%choice%"=="11" (
    "%VENV_PYTHON%" "%SCRIPT%" 50 55
) else if "%choice%"=="12" (
    "%VENV_PYTHON%" "%SCRIPT%" 55 60
) else if "%choice%"=="21" (
    "%VENV_PYTHON%" "%SCRIPT%" 0 20
) else if "%choice%"=="22" (
    "%VENV_PYTHON%" "%SCRIPT%" 20 40
) else if "%choice%"=="23" (
    "%VENV_PYTHON%" "%SCRIPT%" 40 60
) else if "%choice%"=="50" (
    "%VENV_PYTHON%" "%SCRIPT%" 0 60 auto
) else if "%choice%"=="99" (
    "%VENV_PYTHON%" "%SCRIPT%" 0 60
) else if "%choice%"=="0" (
    set /p start="Start number (1-100): "
    set /p end="End number (1-100): "
    set /a start_idx=%start%-1
    "%VENV_PYTHON%" "%SCRIPT%" %start_idx% %end%
) else (
    echo Invalid choice.
    pause
    exit /b 1
)

echo.
echo ======================================================================
echo Batch test completed.
echo Check test_results folder for results.
echo ======================================================================
pause

