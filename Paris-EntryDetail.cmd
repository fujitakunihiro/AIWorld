@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0unreal\scripts\Start-ParisDigitalTwin.ps1" -EntryDetail -Quality Medium
if errorlevel 1 pause
