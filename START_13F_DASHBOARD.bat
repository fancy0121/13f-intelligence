@echo off
setlocal
cd /d "%~dp0"
set "ROOT=%~dp0"
set "PYTHONPATH=%ROOT%src"

echo ============================================
echo  13F Institutional Evidence Dashboard
echo ============================================

where python >nul 2>nul
if errorlevel 1 (
  echo.
  echo [13F Dashboard could not start.]
  echo Reason: Python was not found on PATH.
  echo Next step: install Python 3.11 or newer, then see README_USER.md.
  echo.
  pause
  exit /b 1
)

python -c "import streamlit" >nul 2>nul
if errorlevel 1 (
  echo.
  echo [13F Dashboard could not start.]
  echo Reason: Streamlit is not installed in this Python environment.
  echo Next step: first-time setup instructions are in README_USER.md.
  echo.
  pause
  exit /b 1
)

echo Starting the dashboard...
echo Your browser should open at: http://localhost:8501
echo.
echo To stop the dashboard later, close this window or run STOP_13F_DASHBOARD.bat
echo.

python -m streamlit run app\app.py
set "EXITCODE=%ERRORLEVEL%"
if not "%EXITCODE%"=="0" (
  echo.
  echo [13F Dashboard could not start.]
  echo Reason: the dashboard process exited with code %EXITCODE%.
  echo Next step: check the messages above, then see README_USER.md.
  echo.
  pause
)
exit /b %EXITCODE%

