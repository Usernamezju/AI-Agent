#!/usr/bin/env bash
# =============================================================================
# Package AI Agent Framework as standalone executable (Linux / WSL)
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")"

echo "============================================="
echo "  Packaging AI Agent Framework (Linux)"
echo "============================================="
echo ""

# Ensure PyInstaller is available
if ! python3 -c "import PyInstaller" 2>/dev/null; then
    echo "[*] Installing PyInstaller..."
    pip install pyinstaller
fi

# Clean
rm -rf dist build

echo "[*] Building..."
pyinstaller --noconfirm --clean \
    --name "AI-Agent" \
    --add-data "src:src" \
    --add-data "config:config" \
    --add-data "ui:ui" \
    --add-data "prompts:prompts" \
    --add-data ".chainlit:.chainlit" \
    --add-data "chainlit.md:." \
    --exclude-module tests \
    --exclude-module experiments \
    --exclude-module scripts \
    --hidden-import streamlit \
    --hidden-import chainlit \
    --hidden-import openai \
    --hidden-import dotenv \
    --hidden-import yaml \
    --collect-all streamlit \
    --collect-all chainlit \
    launcher.py

echo ""
echo "============================================="
echo "  Done: dist/AI-Agent/AI-Agent"
echo "============================================="
echo "  Run: ./dist/AI-Agent/AI-Agent"
echo "  Or : cd dist/AI-Agent && ./AI-Agent"
