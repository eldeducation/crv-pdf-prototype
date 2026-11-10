@echo off
cd /d "%~dp0"
py -3.12 --version >nul 2>&1
if not errorlevel 1 (
  py -3.12 start.py
  goto done
)
py -3.11 --version >nul 2>&1
if not errorlevel 1 (
  py -3.11 start.py
  goto done
)
py -3.10 --version >nul 2>&1
if not errorlevel 1 (
  py -3.10 start.py
  goto done
)
python start.py
:done
if errorlevel 1 pause
