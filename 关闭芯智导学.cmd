@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\xzd_supervisor.ps1" -Stop
set "XZD_EXIT_CODE=%ERRORLEVEL%"
if not "%XZD_EXIT_CODE%"=="0" pause
exit /b %XZD_EXIT_CODE%
