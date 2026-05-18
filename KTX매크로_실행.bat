@echo off
chcp 65001 >nul
cd /d "%~dp0"
start "" "C:\Program Files\Python312\pythonw.exe" "%~dp0main.py"
exit
