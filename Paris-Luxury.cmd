@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0unreal\scripts\Start-ParisDigitalTwin.ps1" -DistrictView -DistrictSpot 3 -Quality Medium
