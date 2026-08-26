@echo off
setlocal
cd /d "%~dp0"
set "ROOT=%~dp0"
set "PYTHONPATH=%ROOT%src"

echo ============================================
echo  Update 13F data (requires internet)
echo ============================================
echo This downloads the latest SEC 13F filings for the tracked managers,
echo rebuilds the local database, and refreshes the dashboard data.
echo It may take several minutes. Do not close this window while it runs.
echo.

where python >nul 2>nul
if errorlevel 1 (
  echo.
  echo [Update could not start.]
  echo Reason: Python was not found on PATH.
  echo Next step: install Python 3.11 or newer, then see README_USER.md.
  echo.
  pause
  exit /b 1
)

python scripts\update_data.py
set "EXITCODE=%ERRORLEVEL%"
if not "%EXITCODE%"=="0" (
  echo.
  echo Update failed. Existing dashboard data remains available.
  echo See log: %ROOT%data\last_update.log
)
echo.
pause
exit /b %EXITCODE%

