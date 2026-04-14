#!/bin/bash
# Compound Wiki 快捷启动脚本 (macOS/Linux)
# 使用方法: ./cw.sh <命令>

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/scripts/cw_tool.py"

if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "[错误] 需要 Python 环境"
    echo "请先安装 Python: https://python.org"
    exit 1
fi

if command -v python3 &> /dev/null; then
    python3 "$PYTHON_SCRIPT" "$@"
else
    python "$PYTHON_SCRIPT" "$@"
fi
