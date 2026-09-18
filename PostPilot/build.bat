@echo off
REM PostPilot v1 - build script (run on the Windows laptop)
REM Produces dist\PostPilot\PostPilot.exe (one-dir build: faster start, easier debugging)

setlocal
cd /d "%~dp0"

echo [1/4] Checking Python...
python --version || (echo ERROR: install Python 3.11+ from python.org and re-run. & pause & exit /b 1)

echo [2/4] Installing dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt || (echo ERROR: pip install failed. & pause & exit /b 1)

echo [3/4] Syntax check...
python -m compileall -q app browser accounts inbox uploaders scheduler main.py agent_send.py || (echo ERROR: syntax errors found. & pause & exit /b 1)

echo [4/4] Building with PyInstaller (one-dir)...
python -m PyInstaller --noconfirm --clean ^
  --name PostPilot ^
  --onedir ^
  --windowed ^
  --icon="app\assets\icon.ico" ^
  --add-data "README.md;." ^
  --add-data "app\assets;app\assets" ^
  main.py || (echo ERROR: PyInstaller build failed. & pause & exit /b 1)

echo.
echo BUILD OK: dist\PostPilot\PostPilot.exe
echo Copy the whole dist\PostPilot folder anywhere you like and run PostPilot.exe.
pause
