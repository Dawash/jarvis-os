@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1
title JARVIS-OS

:: Navigate to project root
cd /d "%~dp0"

:: ── Banner ──────────────────────────────────────────────────
cls
echo.
echo      ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗       ██████╗ ███████╗
echo      ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝      ██╔═══██╗██╔════╝
echo      ██║███████║██████╔╝██║   ██║██║███████╗█████╗██║   ██║███████╗
echo ██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║╚════╝██║   ██║╚════██║
echo ╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║      ╚██████╔╝███████║
echo  ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝       ╚═════╝ ╚══════╝
echo.
echo               AI Operating System v2.0
echo               One-Click Launcher
echo.

:: ── Step 1: Check Python ───────────────────────────────────
echo [1/6] Checking Python...
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo   ERROR: Python not found!
    echo   Download from: https://www.python.org/downloads/
    echo   IMPORTANT: Check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do echo   OK: %%i

:: Check version >= 3.10
python -c "import sys; exit(0 if sys.version_info >= (3,10) else 1)" 2>nul
if %ERRORLEVEL% neq 0 (
    echo   ERROR: Python 3.10+ is required.
    echo   Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: ── Step 2: Virtual Environment ────────────────────────────
echo [2/6] Setting up virtual environment...
if not exist "venv" (
    python -m venv venv
    echo   OK: Virtual environment created
) else (
    echo   OK: Virtual environment exists
)

:: Activate
call venv\Scripts\activate.bat

:: ── Step 3: Install Dependencies ──────────────────────────
echo [3/6] Installing dependencies...
pip install --upgrade pip -q 2>nul
pip install -r requirements.txt -q 2>nul
echo   OK: Dependencies installed

:: Optional desktop mode
pip install pywebview -q 2>nul && (
    echo   OK: Desktop mode available
) || (
    echo   NOTE: Desktop mode skipped (optional)
)

:: ── Step 4: Setup .env ────────────────────────────────────
echo [4/6] Checking configuration...
if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env >nul
        echo   OK: .env created from template
    ) else (
        (
            echo # JARVIS-OS Environment Configuration
            echo # Add your API keys below ^(at least one is required^)
            echo.
            echo # OpenAI API Key ^(for GPT-4o^) — get from https://platform.openai.com/api-keys
            echo OPENAI_API_KEY=
            echo.
            echo # Anthropic API Key ^(for Claude^) — get from https://console.anthropic.com/
            echo ANTHROPIC_API_KEY=
            echo.
            echo # Optional: For local LLM, install Ollama from https://ollama.com
            echo # No API key needed — just run: ollama pull llama3
        ) > .env
        echo   NOTE: .env created — add your API keys for LLM features
    )
) else (
    echo   OK: .env exists
)

:: ── Step 5: Create Directories ────────────────────────────
echo [5/6] Preparing directories...
if not exist "logs" mkdir logs
if not exist "data" mkdir data
if not exist "data\uploads" mkdir "data\uploads"
if not exist "memory" mkdir memory
if not exist "plugins" mkdir plugins
echo   OK: Directories ready

:: ── Step 6: Load .env and Launch ──────────────────────────
echo [6/6] Launching JARVIS-OS...

:: Load .env into environment
if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
        set "line=%%a"
        if not "!line:~0,1!"=="#" (
            if not "%%b"=="" set "%%a=%%b"
        )
    )
)

:: Check for API keys
set HAS_KEY=0
if defined OPENAI_API_KEY if not "!OPENAI_API_KEY!"=="" set HAS_KEY=1
if defined ANTHROPIC_API_KEY if not "!ANTHROPIC_API_KEY!"=="" set HAS_KEY=1

if !HAS_KEY!==0 (
    echo.
    echo   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    echo    No API keys found. Starting in offline mode.
    echo    For full features, add keys to .env or install Ollama.
    echo   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    echo.
)

:: Parse mode
set MODE=%1
if "%MODE%"=="" set MODE=--browser

echo.
echo  ═══════════════════════════════════════════════════════
echo   JARVIS-OS is starting on http://localhost:8000
echo   Press Ctrl+C to stop
echo  ═══════════════════════════════════════════════════════
echo.

if "%MODE%"=="--desktop" goto desktop
if "%MODE%"=="-d" goto desktop
if "%MODE%"=="--server" goto server
if "%MODE%"=="-s" goto server
goto browser

:desktop
echo   Mode: Native Desktop
python desktop_launcher.py
goto end

:server
echo   Mode: Server Only (API)
python main.py
goto end

:browser
echo   Mode: Browser (auto-opening)
start "" python -c "import time,webbrowser;time.sleep(3);webbrowser.open('http://localhost:8000')"
python main.py
goto end

:end
endlocal
