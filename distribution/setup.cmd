@echo off
cd /d "%~dp0"
python setup_local.py
if errorlevel 1 pause
