@echo off
chcp 65001 >nul 2>&1
title JARVIS-OS

cd /d "%~dp0\.."

:: Activate virtual environment
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

:: Load .env into environment
if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
        set "line=%%a"
        if not "!line:~0,1!"=="#" (
            set "%%a=%%b"
        )
    )
)

set MODE=%1
if "%MODE%"=="" set MODE=--browser

if "%MODE%"=="--desktop" goto desktop
if "%MODE%"=="-d" goto desktop
if "%MODE%"=="--server" goto server
if "%MODE%"=="-s" goto server
goto browser

:desktop
echo Launching JARVIS-OS in Native Desktop Mode...
python desktop_launcher.py
goto end

:server
echo Starting JARVIS-OS Server...
python main.py
goto end

:browser
echo Launching JARVIS-OS in Browser Mode...
start "" python -c "import time,webbrowser;time.sleep(3);webbrowser.open('http://localhost:8000')"
python main.py
goto end

:end
