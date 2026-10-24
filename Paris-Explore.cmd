@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File ".\unreal\scripts\Start-ParisDigitalTwin.ps1" -Photoreal -ThirdPerson %*
if errorlevel 1 pause
