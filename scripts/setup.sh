#!/usr/bin/env bash
# ╔══════════════════════════════════════════════════════╗
# ║            JARVIS-OS Setup Script                    ║
# ╚══════════════════════════════════════════════════════╝

set -e

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}"
echo "     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗       ██████╗ ███████╗"
echo "     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝      ██╔═══██╗██╔════╝"
echo "     ██║███████║██████╔╝██║   ██║██║███████╗█████╗██║   ██║███████╗"
echo "██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║╚════╝██║   ██║╚════██║"
echo "╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║      ╚██████╔╝███████║"
echo " ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝       ╚═════╝ ╚══════╝"
echo -e "${NC}"
echo -e "${CYAN}              Setup Script v1.0${NC}"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# ── Check Python ─────────────────────────────────────────
echo -e "${YELLOW}[1/5] Checking Python...${NC}"
if command -v python3 &>/dev/null; then
    PYTHON=python3
    PY_VERSION=$($PYTHON --version 2>&1)
    echo -e "  ${GREEN}✓ $PY_VERSION${NC}"
else
    echo -e "  ${RED}✗ Python 3 not found. Please install Python 3.10+${NC}"
    exit 1
fi

# ── Create Virtual Environment ───────────────────────────
echo -e "${YELLOW}[2/5] Creating virtual environment...${NC}"
if [ ! -d "venv" ]; then
    $PYTHON -m venv venv
    echo -e "  ${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "  ${GREEN}✓ Virtual environment already exists${NC}"
fi

# Activate
source venv/bin/activate

# ── Install Dependencies ─────────────────────────────────
echo -e "${YELLOW}[3/5] Installing dependencies...${NC}"
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo -e "  ${GREEN}✓ Core dependencies installed${NC}"

# Optional: native desktop mode
echo -e "${YELLOW}  Installing native desktop support (pywebview)...${NC}"
pip install pywebview -q 2>/dev/null && echo -e "  ${GREEN}✓ pywebview installed${NC}" || echo -e "  ${YELLOW}⚠ pywebview skipped (optional — run in browser mode)${NC}"

# ── Setup .env ───────────────────────────────────────────
echo -e "${YELLOW}[4/5] Configuring environment...${NC}"
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "  ${YELLOW}⚠ .env file created from template${NC}"
    echo -e "  ${YELLOW}  Please edit .env and add your API keys${NC}"
else
    echo -e "  ${GREEN}✓ .env file exists${NC}"
fi

# ── Create directories ───────────────────────────────────
echo -e "${YELLOW}[5/5] Creating data directories...${NC}"
mkdir -p logs data data/uploads memory plugins
echo -e "  ${GREEN}✓ Directories ready${NC}"

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  JARVIS-OS setup complete!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${CYAN}Before starting, edit your .env file:${NC}"
echo -e "    nano .env"
echo ""
echo -e "  ${CYAN}Then launch JARVIS-OS:${NC}"
echo ""
echo -e "  ${GREEN}Native Desktop Mode (fullscreen OS):${NC}"
echo -e "    ./scripts/start.sh --desktop"
echo ""
echo -e "  ${GREEN}Browser Mode:${NC}"
echo -e "    ./scripts/start.sh"
echo ""
echo -e "  ${GREEN}Server Only (API mode):${NC}"
echo -e "    ./scripts/start.sh --server"
echo ""
