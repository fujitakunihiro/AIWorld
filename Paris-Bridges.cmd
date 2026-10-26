@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0unreal\scripts\Start-ParisDigitalTwin.ps1" -BridgeView -Quality Medium
if errorlevel 1 pause
