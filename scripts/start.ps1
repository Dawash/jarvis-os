# ╔══════════════════════════════════════════════════════╗
# ║            JARVIS-OS Launcher — PowerShell           ║
# ╚══════════════════════════════════════════════════════╝

param(
    [ValidateSet("desktop", "browser", "server")]
    [string]$Mode = "browser"
)

$ProjectDir = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectDir

# Activate virtual environment
if (Test-Path "venv\Scripts\Activate.ps1") {
    & "venv\Scripts\Activate.ps1"
}

# Load .env
if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $parts = $line -split "=", 2
            [Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim(), "Process")
        }
    }
}

switch ($Mode) {
    "desktop" {
        Write-Host "Launching JARVIS-OS in Native Desktop Mode..." -ForegroundColor Cyan
        python desktop_launcher.py
    }
    "server" {
        Write-Host "Starting JARVIS-OS Server..." -ForegroundColor Cyan
        python main.py
    }
    "browser" {
        Write-Host "Launching JARVIS-OS in Browser Mode..." -ForegroundColor Cyan
        Start-Job -ScriptBlock {
            Start-Sleep -Seconds 3
            Start-Process "http://localhost:8000"
        } | Out-Null
        python main.py
    }
}
