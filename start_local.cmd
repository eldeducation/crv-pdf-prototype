@echo off
rem Start the local site with the same address as last time and open it in the browser.
rem The address (port and token) is kept in server.local.json; an API key saved
rem with the "save on this PC" checkbox is read back automatically.
rem Close this window to stop the site.
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
python -u server.py --reuse-address --open-browser
pause
