#!/bin/bash
# SafeTensors → GGUF 转换器 启动脚本
# 用法: ./run.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 检查 Python
PYTHON=""
for p in python3 python; do
    if command -v "$p" &>/dev/null; then
        PYTHON="$p"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "错误: 未找到 Python，请先安装 Python 3.8+"
    exit 1
fi

echo "使用 Python: $($PYTHON --version 2>&1)"
echo "启动转换器…"
exec "$PYTHON" converter.py
