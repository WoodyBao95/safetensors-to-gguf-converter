#!/bin/bash
# SafeTensors to GGUF — .app launcher
APP_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
RESOURCES="$APP_DIR/Contents/Resources"

# 查找系统 Python3
PYTHON=""
for p in /usr/local/bin/python3 /opt/homebrew/bin/python3 /usr/bin/python3; do
    if [ -x "$p" ]; then PYTHON="$p"; break; fi
done
if [ -z "$PYTHON" ]; then
    osascript -e 'display dialog "未找到 Python3，请先安装 Python" buttons {"OK"} default button "OK" with icon stop'
    exit 1
fi

# 设置 PYTHONPATH 指向内置依赖
SITE_PKGS="$RESOURCES/deps/lib/python3.14/site-packages"
if [ -d "$SITE_PKGS" ]; then
    export PYTHONPATH="$SITE_PKGS${PYTHONPATH:+:$PYTHONPATH}"
fi

# 强制 arm64 架构运行（torch 是 arm64 only）
exec arch -arm64 "$PYTHON" "$RESOURCES/converter.py" "$@"
