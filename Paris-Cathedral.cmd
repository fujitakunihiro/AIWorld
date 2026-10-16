@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File ".\unreal\scripts\Start-ParisDigitalTwin.ps1" -Photoreal -PhotoCamera Front -Quality High
if errorlevel 1 pause
