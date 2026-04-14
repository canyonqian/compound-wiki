#!/bin/bash
# ============================================
#  Compound Wiki — Auto Agent Launcher
#  Linux/macOS
# ============================================

set -e

CW_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$CW_DIR"

echo "============================================"
echo "  Compound Wiki — Auto Agent"
echo "  Starting intelligent memory system..."
echo "============================================"
echo ""

# Check Python
if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
    echo "[ERROR] Python is not installed"
    echo "Please install Python 3.10+: https://python.org"
    exit 1
fi
PYTHON_CMD=$(command -v python3 || command -v python)

# Install deps if needed
if [ ! -f "$CW_DIR/.installed" ]; then
    echo "[SETUP] Installing required packages..."
    $PYTHON_CMD -m pip install watchdog anthropic openai --quiet 2>/dev/null || true
    touch "$CW_DIR/.installed"
    echo "[OK] Dependencies installed."
    echo ""
fi

# Run agent (default: start)
if [ $# -eq 0 ]; then
    $PYTHON_CMD auto/agent.py start
else
    $PYTHON_CMD auto/agent.py "$@"
fi
