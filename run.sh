#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════════════╗
# ║          JARVIS-OS — One-Click Launcher (Linux/macOS)       ║
# ║          Just run: ./run.sh                                  ║
# ╚══════════════════════════════════════════════════════════════╝

set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# Navigate to project root (works even if run from another directory)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Banner ──────────────────────────────────────────────────────
clear 2>/dev/null || true
echo -e "${CYAN}"
echo "     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗       ██████╗ ███████╗"
echo "     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝      ██╔═══██╗██╔════╝"
echo "     ██║███████║██████╔╝██║   ██║██║███████╗█████╗██║   ██║███████╗"
echo "██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║╚════╝██║   ██║╚════██║"
echo "╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║      ╚██████╔╝███████║"
echo " ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝       ╚═════╝ ╚══════╝"
echo -e "${NC}"
echo -e "${BOLD}              AI Operating System v2.0${NC}"
echo -e "${DIM}              One-Click Launcher${NC}"
echo ""

# ── Step 1: Check Python ───────────────────────────────────────
echo -e "${YELLOW}[1/6] Checking Python...${NC}"
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        PY_VER=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null)
        PY_MAJOR=$("$cmd" -c "import sys; print(sys.version_info.major)" 2>/dev/null)
        PY_MINOR=$("$cmd" -c "import sys; print(sys.version_info.minor)" 2>/dev/null)
        if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 10 ] 2>/dev/null; then
            PYTHON="$cmd"
            echo -e "  ${GREEN}✓ Found $cmd ($PY_VER)${NC}"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo -e "  ${RED}✗ Python 3.10+ is required but not found.${NC}"
    echo -e "  ${RED}  Install from: https://www.python.org/downloads/${NC}"
    exit 1
fi

# ── Step 2: Create virtual environment ─────────────────────────
echo -e "${YELLOW}[2/6] Setting up virtual environment...${NC}"
if [ ! -d "venv" ]; then
    $PYTHON -m venv venv
    echo -e "  ${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "  ${GREEN}✓ Virtual environment exists${NC}"
fi

# Activate
source venv/bin/activate

# ── Step 3: Install dependencies ──────────────────────────────
echo -e "${YELLOW}[3/6] Installing dependencies...${NC}"
pip install --upgrade pip -q 2>/dev/null
if pip install -r requirements.txt -q 2>/dev/null; then
    echo -e "  ${GREEN}✓ All dependencies installed${NC}"
else
    echo -e "  ${YELLOW}⚠ Some optional dependencies may have failed (non-critical)${NC}"
    pip install -r requirements.txt --ignore-installed 2>/dev/null || true
fi

# Optional: native desktop mode
pip install pywebview -q 2>/dev/null && echo -e "  ${GREEN}✓ Desktop mode available${NC}" || echo -e "  ${DIM}  Desktop mode skipped (optional)${NC}"

# ── Step 4: Setup .env ────────────────────────────────────────
echo -e "${YELLOW}[4/6] Checking configuration...${NC}"
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "  ${GREEN}✓ .env created from template${NC}"
    else
        cat > .env << 'ENVEOF'
# JARVIS-OS Environment Configuration
# Add your API keys below (at least one is required)

# OpenAI API Key (for GPT-4o) — get from https://platform.openai.com/api-keys
OPENAI_API_KEY=

# Anthropic API Key (for Claude) — get from https://console.anthropic.com/
ANTHROPIC_API_KEY=

# Optional: For local LLM, install Ollama from https://ollama.com
# No API key needed — just run: ollama pull llama3
ENVEOF
        echo -e "  ${YELLOW}⚠ .env created — add your API keys before using LLM features${NC}"
    fi
else
    echo -e "  ${GREEN}✓ .env exists${NC}"
fi

# ── Step 5: Create directories ────────────────────────────────
echo -e "${YELLOW}[5/6] Preparing directories...${NC}"
mkdir -p logs data data/uploads memory plugins
echo -e "  ${GREEN}✓ All directories ready${NC}"

# ── Step 6: Load env and launch ───────────────────────────────
echo -e "${YELLOW}[6/6] Launching JARVIS-OS...${NC}"

# Load .env
if [ -f ".env" ]; then
    set -a
    source .env 2>/dev/null || true
    set +a
fi

# Check for API keys
HAS_KEY=false
if [ -n "$OPENAI_API_KEY" ] && [ "$OPENAI_API_KEY" != "" ]; then HAS_KEY=true; fi
if [ -n "$ANTHROPIC_API_KEY" ] && [ "$ANTHROPIC_API_KEY" != "" ]; then HAS_KEY=true; fi

if [ "$HAS_KEY" = false ]; then
    echo ""
    echo -e "  ${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "  ${YELLOW}  No API keys found. JARVIS will start in offline mode.${NC}"
    echo -e "  ${YELLOW}  For full features, add keys to .env file or install${NC}"
    echo -e "  ${YELLOW}  Ollama (https://ollama.com) for local LLM support.${NC}"
    echo -e "  ${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
fi

# Parse launch mode
MODE="${1:-browser}"
PORT=$(python -c "
import yaml
try:
    with open('config/settings.yaml') as f:
        print(yaml.safe_load(f).get('server',{}).get('port', 8000))
except:
    print(8000)
" 2>/dev/null || echo 8000)

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  JARVIS-OS is starting on http://localhost:${PORT}${NC}"
echo -e "${GREEN}  Press Ctrl+C to stop${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
echo ""

case "$MODE" in
    --desktop|-d)
        echo -e "  ${CYAN}Mode: Native Desktop${NC}"
        python desktop_launcher.py
        ;;
    --server|-s)
        echo -e "  ${CYAN}Mode: Server Only (API)${NC}"
        python main.py
        ;;
    --browser|-b|*)
        echo -e "  ${CYAN}Mode: Browser (auto-opening)${NC}"
        # Open browser after 3-second delay
        (sleep 3 && python -c "import webbrowser; webbrowser.open('http://localhost:$PORT')" 2>/dev/null) &
        python main.py
        ;;
esac
