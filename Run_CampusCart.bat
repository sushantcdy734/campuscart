@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo        Starting CampusCart...
echo ============================================

where py >nul 2>nul
if %errorlevel%==0 (
  set PYTHON=py
) else (
  set PYTHON=python
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating virtual environment...
  %PYTHON% -m venv .venv
  if errorlevel 1 goto :error
)

echo Installing/checking dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo.
echo CampusCart is starting...
echo Open: http://127.0.0.1:5000
start "" http://127.0.0.1:5000
".venv\Scripts\python.exe" app.py

goto :end
:error
echo.
echo Failed to start CampusCart. Make sure Python is installed.
pause
:end
endlocal
