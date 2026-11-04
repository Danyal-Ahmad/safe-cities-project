@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Safe City FYP - Server

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

echo ========================================
echo   SAFE CITY FYP - DEVELOPMENT SERVER
echo ========================================
echo   Public:  http://127.0.0.1:8000/
echo   Staff:   http://127.0.0.1:8000/auth/admin/login/
echo   Citizen: http://127.0.0.1:8000/auth/citizen/login/
echo.
echo   Press CTRL+C to stop
echo ========================================
echo.
echo   Create the first admin with: python manage.py createsuperuser
echo\.

".venv\Scripts\python.exe" manage.py migrate --noinput
".venv\Scripts\python.exe" manage.py runserver 0.0.0.0:8000
pause
