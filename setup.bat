@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Safe Cities Project - Setup

echo ========================================
echo   SAFE CITIES PROJECT - FIRST-TIME SETUP
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

echo [3/8] Installing core requirements (CPU baseline)...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo [ERROR] Core pip install failed.
  pause
  exit /b 1
)

echo [4/8] GPU acceleration: trying onnxruntime-gpu (NVIDIA CUDA)...
".venv\Scripts\python.exe" -m pip install "onnxruntime-gpu>=1.17" 2>nul
if errorlevel 1 (
  echo [INFO] onnxruntime-gpu unavailable - AI models will run on CPU. This is fine.
) else (
  ".venv\Scripts\python.exe" -c "import onnxruntime as ort; ps=ort.get_available_providers(); print('  [OK] onnxruntime providers:', ', '.join(ps)); import sys; sys.exit(0 if 'CUDAExecutionProvider' in ps else 1)" 2>nul
  if errorlevel 1 (
    echo [INFO] CUDA not detected - uninstalling GPU build, keeping CPU onnxruntime.
    ".venv\Scripts\python.exe" -m pip uninstall -y onnxruntime-gpu 2>nul
    ".venv\Scripts\python.exe" -m pip install "onnxruntime>=1.17" 2>nul
  ) else (
    echo [OK] GPU inference enabled. Models run on CUDA with automatic CPU fallback.
  )
)

echo [5/8] Optional OCR: trying PaddlePaddle (Python 3.10-3.12 only)...
".venv\Scripts\python.exe" -m pip install "paddlepaddle>=2.5.0,<3.0" "paddleocr>=2.7.0,<3" 2>nul
if errorlevel 1 (
  echo [INFO] PaddleOCR skipped - not available for this Python. EasyOCR / Tesseract will be used.
) else (
  echo [OK] PaddleOCR installed.
)

echo [6/8] Running migrations...
".venv\Scripts\python.exe" manage.py migrate --noinput
if errorlevel 1 (
  echo [ERROR] migrate failed.
  pause
  exit /b 1
)

echo [7/8] Collecting static assets...
".venv\Scripts\python.exe" manage.py collectstatic --noinput
if errorlevel 1 (
  echo [ERROR] collectstatic failed.
  pause
  exit /b 1
)

echo [8/8] Creating initial DIG admin (if missing)...
".venv\Scripts\python.exe" manage.py create_dig_admin
if errorlevel 1 (
  echo [ERROR] DIG admin seeding failed.
  pause
  exit /b 1
)

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
