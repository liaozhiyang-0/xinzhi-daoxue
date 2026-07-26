@echo off
setlocal
cd /d "%~dp0"
title Xinzhi Daoxue

if exist "%~dp0.venv\Scripts\python.exe" goto launch_venv

where py.exe >nul 2>nul
if errorlevel 1 goto launch_python
py.exe -3.13 -c "import sys" >nul 2>nul
if not errorlevel 1 goto launch_py313
py.exe -3.12 -c "import sys" >nul 2>nul
if not errorlevel 1 goto launch_py312
py.exe -3.11 -c "import sys" >nul 2>nul
if not errorlevel 1 goto launch_py311

:launch_python
where python.exe >nul 2>nul
if errorlevel 1 goto missing_python
python.exe "%~dp0scripts\team_launcher.py" start --open-browser
goto finished

:launch_py313
py.exe -3.13 "%~dp0scripts\team_launcher.py" start --open-browser
goto finished

:launch_py312
py.exe -3.12 "%~dp0scripts\team_launcher.py" start --open-browser
goto finished

:launch_py311
py.exe -3.11 "%~dp0scripts\team_launcher.py" start --open-browser
goto finished

:launch_venv
"%~dp0.venv\Scripts\python.exe" "%~dp0scripts\team_launcher.py" start --open-browser
goto finished

:missing_python
echo Python 3.11-3.13 is required.
echo Install Python and then double-click this file again.
pause
exit /b 1

:finished
set "XZD_EXIT_CODE=%ERRORLEVEL%"
if not "%XZD_EXIT_CODE%"=="0" pause
exit /b %XZD_EXIT_CODE%
