@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0xzd.ps1" %*
exit /b %ERRORLEVEL%
