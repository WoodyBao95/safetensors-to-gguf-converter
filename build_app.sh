#!/bin/bash
# 一键构建 SafeTensors to GGUF.app
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== SafeTensors to GGUF 构建脚本 ==="

# 1. 查找 Python
PYTHON=""
for p in /usr/local/bin/python3 /opt/homebrew/bin/python3 /usr/bin/python3; do
    if [ -x "$p" ]; then PYTHON="$p"; break; fi
done
if [ -z "$PYTHON" ]; then
    echo "错误: 未找到 Python3"; exit 1
fi
echo "使用 Python: $PYTHON ($($PYTHON --version 2>&1))"

# 2. 创建依赖环境
DEPS="$SCRIPT_DIR/deps"
if [ -d "$DEPS/lib" ]; then
    echo "依赖目录已存在，跳过安装（如需重装请删除 deps/ 目录）"
else
    echo "正在创建依赖环境…"
    "$PYTHON" -m venv "$DEPS"
    "$DEPS/bin/pip" install --upgrade pip --quiet

    echo "正在安装 Python 依赖…"
    "$DEPS/bin/pip" install \
        "numpy~=1.26.4" \
        "sentencepiece>=0.1.98,<0.3.0" \
        "transformers>=4.40.0" \
        "gguf>=0.1.0" \
        "protobuf>=4.21.0,<5.0.0" \
        "safetensors>=0.4.0" \
        "huggingface_hub>=0.20.0" \
        --quiet

    echo "正在安装 PyTorch (CPU)…"
    "$DEPS/bin/pip" install torch --index-url https://download.pytorch.org/whl/cpu --quiet

    # 清理
    echo "正在精简依赖…"
    SP="$DEPS/lib/python3.14/site-packages"
    find "$SP" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
    find "$SP" -name "*.pyc" -delete 2>/dev/null
    rm -rf "$SP/torch/test" 2>/dev/null
fi

# 3. 构建 .app
APP="$SCRIPT_DIR/SafeTensors to GGUF.app"
echo "正在构建 .app…"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources/deps/lib"

cp "$SCRIPT_DIR/launcher.sh" "$APP/Contents/MacOS/launcher"
chmod +x "$APP/Contents/MacOS/launcher"
cp "$SCRIPT_DIR/Info.plist" "$APP/Contents/Info.plist"
cp "$SCRIPT_DIR/converter.py" "$APP/Contents/Resources/converter.py"
cp -a "$SCRIPT_DIR/deps/lib/python3.14" "$APP/Contents/Resources/deps/lib/python3.14"

# 复制 Python 图标
PYTHON_ICON="/Library/Frameworks/Python.framework/Versions/3.14/Resources/Python.app/Contents/Resources/PythonApplet.icns"
if [ -f "$PYTHON_ICON" ]; then
    cp "$PYTHON_ICON" "$APP/Contents/Resources/AppIcon.icns"
fi

# 同步 Info.plist 图标设置
if [ -f "$APP/Contents/Resources/AppIcon.icns" ]; then
    /usr/libexec/PlistBuddy -c "Add :CFBundleIconFile string AppIcon" "$APP/Contents/Info.plist" 2>/dev/null || \
    /usr/libexec/PlistBuddy -c "Set :CFBundleIconFile AppIcon" "$APP/Contents/Info.plist"
fi

echo ""
echo "=== 构建完成 ==="
echo "应用位置: $APP"
echo "应用大小: $(du -sh "$APP" | cut -f1)"
echo ""
echo "运行: open \"$APP\""
