@echo off
cd /d "%~dp0"
if exist "%~dp0runtime\pythonw.exe" (
 start "" "%~dp0runtime\pythonw.exe" "%~dp0android_location_test.py"
) else (
 py -3.13 -X utf8 "%~dp0android_location_test.py"
)
