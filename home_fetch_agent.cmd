@echo off
rem Double-click while you work: lets the cloud app fetch YouTube links via this PC.
cd /d "%~dp0"
python home_fetch_agent.py
pause
