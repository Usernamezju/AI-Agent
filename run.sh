#!/usr/bin/env bash
# =============================================================================
# AI Agent Framework — one-click launcher (Linux / macOS / WSL)
#
# Usage:
#   ./run.sh              → Streamlit Web UI (default)
#   ./run.sh cli          → CLI interactive mode
#   ./run.sh install      → Only install dependencies, don't launch
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# ---- colours ----
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  AI Agent Framework — ReAct${NC}"
echo -e "${GREEN}  浙江大学人工智能基础实验${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# ---- Python check ----
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}[ERROR] python3 not found. Install Python ≥3.10 first.${NC}"
    exit 1
fi
PY="$(command -v python3)"
echo -e "[OK] Python: $($PY --version)"

# ---- .env check ----
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}[!] .env not found — creating from template.${NC}"
    cat > .env <<'EOF'
DEEPSEEK_API_KEY=sk-your-key-here
SANDBOX_ROOT=./sandbox
EOF
    echo -e "${YELLOW}    Edit .env and paste your DeepSeek API key, then re-run.${NC}"
    exit 0
fi

if grep -q 'sk-your-key-here' .env 2>/dev/null; then
    echo -e "${YELLOW}[!] You still have the placeholder API key in .env.${NC}"
    echo -e "${YELLOW}    Edit .env and use a real key from https://platform.deepseek.com${NC}"
fi

# ---- dependencies ----
install_deps() {
    echo ""
    echo -e "${GREEN}[*] Installing dependencies ...${NC}"
    $PY -m pip install -q -r requirements.txt 2>&1 | tail -3
    echo -e "${GREEN}[OK] Dependencies ready.${NC}"
}

MODE="${1:-web}"

if [ "$MODE" = "install" ]; then
    install_deps
    echo ""
    echo "Dependencies installed. Run ./run.sh to start."
    exit 0
fi

install_deps

# ---- launch ----
echo ""
if [ "$MODE" = "cli" ]; then
    echo -e "${GREEN}[*] Starting CLI mode ...${NC}"
    exec $PY scripts/run_agent.py
else
    echo -e "${GREEN}[*] Starting Web UI ...${NC}"
    echo -e "    Open ${YELLOW}http://localhost:8501${NC} in your browser"
    echo ""
    exec streamlit run ui/app.py --server.headless true
fi
