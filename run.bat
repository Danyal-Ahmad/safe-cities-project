@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Safe Cities Project - Server

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Virtual environment missing. Run setup.bat first.
  pause
  exit /b 1
)

if not exist ".env" (
  if exist ".env.example" (
    copy /Y ".env.example" ".env" >nul
    echo [INFO] Created .env from .env.example
  )
)

set PY=".venv\Scripts\python.exe"
set DEBUG_MODE=1
%PY% -c "import os,sys; sys.exit(0 if os.environ.get('DEBUG','True').strip().lower() in ('1','true','yes','on','y','t') else 1)" 2>nul
if errorlevel 1 set DEBUG_MODE=0

echo ========================================
if "%DEBUG_MODE%"=="1" (
  echo   SAFE CITIES PROJECT - DEVELOPMENT SERVER
) else (
  echo   SAFE CITIES PROJECT - PRODUCTION SERVER
)
echo ========================================
echo   Public:  http://127.0.0.1:8000/
echo   Staff:   http://127.0.0.1:8000/auth/admin/login/
echo   Citizen: http://127.0.0.1:8000/auth/citizen/login/
echo.
echo   Press CTRL+C to stop
echo ========================================
echo.

%PY% manage.py migrate --noinput
if errorlevel 1 (
  echo [ERROR] migrate failed.
  pause
  exit /b 1
)

if "%DEBUG_MODE%"=="0" (
  %PY% manage.py collectstatic --noinput
  if errorlevel 1 (
    echo [ERROR] collectstatic failed.
    pause
    exit /b 1
  )
  %PY% -m gunicorn -c deploy/gunicorn.conf.py wrongway_system.wsgi:application
) else (
  %PY% manage.py runserver 0.0.0.0:8000 --nostatic
)
pause
