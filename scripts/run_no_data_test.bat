@echo off
setlocal
chcp 65001 > nul

rem 프로젝트 루트로 이동
cd /d "%~dp0"

echo ======================================================================
echo   Data Absence Test (Hallucination Detection)
echo ======================================================================
echo.
echo [Purpose]
echo This test queries for data that does NOT exist in GDB.
echo All responses should be "data not found" - NOT numbers!
echo.
echo [Test Items]
echo - Cash Flow (Operating/Investing/Financing)
echo - EBITDA / EBITDA Margin
echo - Turnover Ratios (Working Capital, Inventory, AR)
echo - ROA, ROIC
echo - R-D Expenses, Depreciation
echo - Other missing accounts
echo.
echo Total: 20 questions
echo Expected: 20 "no data" responses
echo.
echo ======================================================================
echo.

set "VENV_PYTHON=venv\Scripts\python.exe"
set "SCRIPT=test_no_data_queries.py"

if not exist "%VENV_PYTHON%" (
    echo [ERROR] Virtual environment not found.
    pause
    exit /b 1
)

"%VENV_PYTHON%" "%SCRIPT%"

echo.
echo ======================================================================
echo Test completed. Check test_results folder.
echo ======================================================================
pause


