@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0local\windows\setup.ps1"
echo.
echo Setup finished. Check the RESULT lines above.
pause
