@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Safe City FYP - Setup

echo ========================================
echo   SAFE CITY FYP - FIRST-TIME SETUP
echo ========================================
echo.

where python >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python not found on PATH. Install Python 3.11 or 3.12 (recommended) and retry.
  pause
  exit /b 1
)

python -c "import sys; print('Using Python', sys.version)"
echo.

if not exist ".env" (
  if exist ".env.example" (
    copy /Y ".env.example" ".env" >nul
    echo [INFO] Created .env from .env.example
  ) else (
    echo [ERROR] .env.example missing.
    pause
    exit /b 1
  )
)

if not exist ".venv\Scripts\python.exe" (
  echo [1/8] Creating virtual environment...
  python -m venv .venv
  if errorlevel 1 (
    echo [ERROR] venv failed.
    pause
    exit /b 1
  )
) else (
  echo [1/8] Virtual environment already exists.
)

echo [2/8] Upgrading pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip wheel setuptools

echo [3/8] Installing core requirements...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo [ERROR] Core pip install failed.
  pause
  exit /b 1
)

echo [4/8] Optional OCR: trying PaddlePaddle (Python 3.10-3.12 only)...
".venv\Scripts\python.exe" -m pip install "paddlepaddle>=2.5.0,<3.0" "paddleocr>=2.7.0,<3" 2>nul
if errorlevel 1 (
  echo [INFO] PaddleOCR skipped - not available for this Python. EasyOCR / Tesseract will be used.
) else (
  echo [OK] PaddleOCR installed.
)

echo [5/8] Running migrations...
".venv\Scripts\python.exe" manage.py migrate --noinput
if errorlevel 1 (
  echo [ERROR] migrate failed.
  pause
  exit /b 1
)

echo [6/8] Seeding cameras...



echo.
echo ========================================
echo   SETUP COMPLETE
echo ========================================
echo   URL:       http://127.0.0.1:8000/
echo   Staff:     /auth/admin/login/  (Email + Password)
echo   Citizen:   /auth/citizen/login/ (CNIC + Password)
echo   Start:     run.bat
echo   Superuser: .venv\Scripts\python.exe manage.py createsuperuser
echo ========================================
pause
