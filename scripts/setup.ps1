# ╔══════════════════════════════════════════════════════╗
# ║            JARVIS-OS Setup — PowerShell              ║
# ╚══════════════════════════════════════════════════════╝

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectDir

Write-Host ""
Write-Host "  JARVIS-OS Setup" -ForegroundColor Cyan
Write-Host "  ═══════════════════════════════════════" -ForegroundColor DarkCyan
Write-Host ""

# ── Check Python ─────────────────────────────────────────
Write-Host "[1/5] Checking Python..." -ForegroundColor Yellow
try {
    $pyVersion = python --version 2>&1
    Write-Host "  OK: $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Python not found. Install Python 3.10+ from python.org" -ForegroundColor Red
    Write-Host "  Make sure 'Add Python to PATH' is checked during installation." -ForegroundColor Red
    exit 1
}

# ── Create Virtual Environment ───────────────────────────
Write-Host "[2/5] Creating virtual environment..." -ForegroundColor Yellow
if (-not (Test-Path "venv")) {
    python -m venv venv
    Write-Host "  OK: Virtual environment created" -ForegroundColor Green
} else {
    Write-Host "  OK: Virtual environment exists" -ForegroundColor Green
}

# Activate
& "venv\Scripts\Activate.ps1"

# ── Install Dependencies ─────────────────────────────────
Write-Host "[3/5] Installing dependencies..." -ForegroundColor Yellow
pip install --upgrade pip -q
pip install -r requirements.txt -q
Write-Host "  OK: Dependencies installed" -ForegroundColor Green

Write-Host "  Installing native desktop support..." -ForegroundColor Yellow
try {
    pip install pywebview -q 2>$null
    Write-Host "  OK: pywebview installed" -ForegroundColor Green
} catch {
    Write-Host "  NOTE: pywebview skipped (optional)" -ForegroundColor DarkYellow
}

# ── Setup .env ───────────────────────────────────────────
Write-Host "[4/5] Configuring environment..." -ForegroundColor Yellow
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "  NOTE: .env created. API keys will be requested on first launch." -ForegroundColor DarkYellow
} else {
    Write-Host "  OK: .env file exists" -ForegroundColor Green
}

# ── Create directories ───────────────────────────────────
Write-Host "[5/5] Creating data directories..." -ForegroundColor Yellow
@("logs", "data", "data\uploads", "memory") | ForEach-Object {
    if (-not (Test-Path $_)) { New-Item -ItemType Directory -Path $_ -Force | Out-Null }
}
Write-Host "  OK: Directories ready" -ForegroundColor Green

Write-Host ""
Write-Host "  ═══════════════════════════════════════" -ForegroundColor Green
Write-Host "  JARVIS-OS setup complete!" -ForegroundColor Green
Write-Host "  ═══════════════════════════════════════" -ForegroundColor Green
Write-Host ""
Write-Host "  Launch commands:" -ForegroundColor Cyan
Write-Host "    .\scripts\start.ps1 -Mode desktop   (native fullscreen)" -ForegroundColor White
Write-Host "    .\scripts\start.ps1 -Mode browser   (opens in browser)" -ForegroundColor White
Write-Host "    .\scripts\start.ps1 -Mode server    (API server only)" -ForegroundColor White
Write-Host ""
Write-Host "  API keys will be requested on first launch." -ForegroundColor DarkYellow
Write-Host ""
