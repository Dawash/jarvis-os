@echo off
chcp 65001 >nul 2>&1
title JARVIS-OS Setup

echo.
echo  ╔══════════════════════════════════════════════════════╗
echo  ║            JARVIS-OS Setup — Windows                 ║
echo  ╚══════════════════════════════════════════════════════╝
echo.

cd /d "%~dp0\.."

:: ── Check Python ─────────────────────────────────────────
echo [1/5] Checking Python...
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo   ERROR: Python not found. Please install Python 3.10+ from python.org
    echo   Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo   OK: %%i

:: ── Create Virtual Environment ───────────────────────────
echo [2/5] Creating virtual environment...
if not exist "venv" (
    python -m venv venv
    echo   OK: Virtual environment created
) else (
    echo   OK: Virtual environment already exists
)

:: Activate
call venv\Scripts\activate.bat

:: ── Install Dependencies ─────────────────────────────────
echo [3/5] Installing dependencies...
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo   OK: Core dependencies installed

echo   Installing native desktop support (pywebview)...
pip install pywebview -q 2>nul && (
    echo   OK: pywebview installed
) || (
    echo   NOTE: pywebview skipped — will run in browser mode
)

:: ── Setup .env ───────────────────────────────────────────
echo [4/5] Configuring environment...
if not exist ".env" (
    copy .env.example .env >nul
    echo   NOTE: .env file created. API keys will be requested on first launch.
) else (
    echo   OK: .env file exists
)

:: ── Create directories ───────────────────────────────────
echo [5/5] Creating data directories...
if not exist "logs" mkdir logs
if not exist "data" mkdir data
if not exist "data\uploads" mkdir data\uploads
if not exist "memory" mkdir memory
echo   OK: Directories ready

echo.
echo  ═══════════════════════════════════════════════════════
echo   JARVIS-OS setup complete!
echo  ═══════════════════════════════════════════════════════
echo.
echo   Launch JARVIS-OS:
echo.
echo     Desktop Mode:   scripts\start.bat --desktop
echo     Browser Mode:   scripts\start.bat
echo     Server Only:    scripts\start.bat --server
echo.
echo   API keys will be requested on first launch.
echo.
pause
