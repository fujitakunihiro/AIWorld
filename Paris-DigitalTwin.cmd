@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -File "%~dp0unreal\scripts\Start-ParisDigitalTwin.ps1"
if errorlevel 1 pause
