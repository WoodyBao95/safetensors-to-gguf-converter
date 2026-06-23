# SafeTensors to GGUF Converter

基于 [llama.cpp](https://github.com/ggerganov/llama.cpp) 的 macOS 图形化工具，将 HuggingFace SafeTensors 模型转换为 GGUF 格式，并支持多种量化选项。

参考文章：[开源大模型safetensors格式转gguf](https://blog.csdn.net/weixin_46248339/article/details/139502733)

## 功能特性

- 🖥️ **图形化操作** — 无需命令行，选择文件即可转换
- 📦 **依赖内置** — 所有 Python 依赖（PyTorch、Transformers 等）已打包进 .app，无需手动安装
- 🔧 **26 种量化类型** — 支持 F16 / Q8_0 / Q6_K / Q5_K_M / Q4_K_M / Q3_K / Q2_K / IQ 系列等
- 📊 **实时日志** — 转换过程实时显示进度和日志输出
- ⏹️ **中途停止** — 支持随时取消转换操作
- 🤖 **自动注入 Chat Template** — 检测缺少 chat template 的 Llama 3 模型并自动补全，解决模型对话不停止的问题
- 🔑 **完整特殊 token** — 使用 `--special` 参数确保 `<|eot_id|>` 等所有特殊 token 写入 GGUF

## 下载安装

从 [Releases](../../releases) 页面下载最新版本：

- **`.dmg`** — 双击打开，将 app 拖入 Applications
- **`.pkg`** — 双击运行安装向导，自动安装到 Applications

## 使用方法

### 前置条件

- macOS 10.15+ (Apple Silicon)
- Python 3.8+（系统自带或通过 Homebrew 安装）
- [llama.cpp](https://github.com/ggerganov/llama.cpp) 已编译

### 编译 llama.cpp

```bash
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp
pip install cmake
python3 -m cmake -B build -DCMAKE_BUILD_TYPE=Release
python3 -m cmake --build build --config Release
```

### 转换步骤

1. **打开应用** — 双击 `SafeTensors to GGUF.app`
2. **选择 llama.cpp 目录** — 包含 `convert_hf_to_gguf.py` 和 `build/bin/llama-quantize` 的根目录
3. **选择模型目录** — 包含 `.safetensors` 文件和 `config.json` 的文件夹（从 HuggingFace 或 ModelScope 下载的模型）
4. **选择输出目录** — GGUF 文件保存位置（默认为模型目录）
5. **选择量化类型** — 推荐 `Q4_K_M`（质量和大小的最佳平衡）
6. **点击「开始转换」**

### 转换流程

应用自动执行两步：

```
SafeTensors → F16 GGUF（格式转换）→ Q4_K_M GGUF（量化压缩）
```

### 量化类型参考

| 类型 | 位宽 | 说明 | 推荐场景 |
|------|------|------|----------|
| F16 | 16-bit | 无量化，仅格式转换 | 需要最高精度 |
| Q8_0 | 8-bit | 质量最高 | 质量优先 |
| Q6_K | 6-bit | K-quant | 较好平衡 |
| Q5_K_M | 5-bit | K-quant Medium | 平衡选择 |
| **Q4_K_M** | **4-bit** | **K-quant Medium** | **推荐** |
| Q4_0 | 4-bit | v0 兼容格式 | 兼容性最好 |
| Q3_K_M | 3-bit | K-quant Medium | 追求小体积 |
| Q2_K | 2-bit | K-quant | 极限压缩 |

## 项目结构

```
safetensors-to-gguf-converter/
├── converter.py          # GUI 主程序（tkinter）
├── launcher.sh           # .app 启动脚本
├── Info.plist            # macOS App 配置
├── build_app.sh          # 一键构建 .app 脚本
├── deps/                 # Python 依赖（运行 build_app.sh 生成）
│   └── lib/python3.14/site-packages/
│       ├── torch/
│       ├── transformers/
│       ├── gguf/
│       └── ...
└── README.md
```

## 从源码构建

```bash
# 克隆项目
git clone https://github.com/WoodyBao95/safetensors-to-gguf-converter.git
cd safetensors-to-gguf-converter

# 一键构建 .app（自动安装依赖 + 打包）
chmod +x build_app.sh
./build_app.sh

# 构建完成后 .app 在当前目录
open "SafeTensors to GGUF.app"
```

## 技术方案

- **GUI**: Python tkinter
- **格式转换**: llama.cpp 的 `convert_hf_to_gguf.py`
- **量化**: llama.cpp 的 `llama-quantize` 工具
- **打包**: 手动构建 macOS .app bundle，shell launcher + PYTHONPATH 注入内置依赖
- **架构**: arm64（Apple Silicon 原生）

## 相关链接

- [llama.cpp](https://github.com/ggerganov/llama.cpp) — 转换和量化工具
- [HuggingFace](https://huggingface.co/models) — 模型下载
- [ModelScope](https://modelscope.cn/models) — 国内模型下载
- [参考文章](https://blog.csdn.net/weixin_46248339/article/details/139502733) — safetensors 转 gguf 教程

## License

MIT

## 更新日志

### v1.1.0 (2026-06-23)

- 🐛 **修复: 模型对话不停止** — 转换时自动注入缺失的 chat template，解决 Llama 3 等模型在 llama-server 中无法正常停止的问题
- ✨ **新增: `--special` 参数** — 转换时自动传入 `--special` 确保所有特殊 token（包括 `<|eot_id|>`、`<|start_header_id|>` 等）完整写入 GGUF
- ✨ **新增: 自动检测 Llama 3 模型** — 当模型目录缺少 `chat_template` 时，自动检测架构并注入标准 Llama 3 chat template

### v1.0.0 (2026-06-23)

- 🎉 初始发布
- 🖥️ macOS 图形化界面 (tkinter)
- 📦 依赖内置，无需手动安装
- 🔧 支持 26 种量化类型
- 📊 实时日志输出
- ⏹️ 支持中途停止
