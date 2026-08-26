@echo off
setlocal
echo Stopping the 13F Dashboard (port 8501)...
set "FOUND="
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8501" ^| findstr "LISTENING"') do (
  set "FOUND=1"
  taskkill /PID %%a /F >nul 2>nul
)
if not defined FOUND (
  echo No dashboard process was found on port 8501.
  echo If the dashboard is running in a terminal window, just close that window.
)
echo.
pause

