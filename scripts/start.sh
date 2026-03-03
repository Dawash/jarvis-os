#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════╗
# ║            JARVIS-OS Launcher                        ║
# ╚══════════════════════════════════════════════════════╝

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Activate virtual environment
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Load .env
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

MODE="${1:-browser}"

case "$MODE" in
    --desktop|-d)
        echo "Launching JARVIS-OS in Native Desktop Mode..."
        python desktop_launcher.py
        ;;
    --server|-s)
        echo "Starting JARVIS-OS Server..."
        python main.py
        ;;
    --browser|-b|*)
        echo "Launching JARVIS-OS in Browser Mode..."
        python -c "
import threading, time, webbrowser
from config import load_config
config = load_config()
port = config['server']['port']
def open_browser():
    time.sleep(2)
    webbrowser.open(f'http://localhost:{port}')
threading.Thread(target=open_browser, daemon=True).start()
" &
        python main.py
        ;;
esac
