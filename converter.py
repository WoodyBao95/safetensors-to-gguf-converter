#!/usr/bin/env python3
"""
SafeTensors to GGUF Converter — macOS App
所有依赖已内置，无需安装。
"""

import os
import sys
import json
import subprocess
import threading
import queue
import time
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from pathlib import Path
from datetime import datetime

# ============================================================
# 常量
# ============================================================
APP_NAME = "SafeTensors to GGUF"
CONFIG_FILE = Path.home() / ".safetensors_gguf_converter.json"
DEFAULT_LLAMA_CPP = Path.home() / "Downloads" / "llama.cpp"

# 内置 Python 路径（打包在 .app 内部）
BUNDLED_DEPS = None
if getattr(sys, "frozen", False):
    # PyInstaller 打包后
    _base = Path(sys._MEIPASS)
    BUNDLED_DEPS = _base / "deps"
else:
    # 开发模式
    _dev_deps = Path(__file__).parent / "deps"
    if _dev_deps.is_dir():
        BUNDLED_DEPS = _dev_deps

QUANT_TYPES = {
    "F16 (无量化，仅转格式)": "F16",
    "Q8_0 (8-bit，质量最高)": "Q8_0",
    "Q6_K (6-bit K-quant)": "Q6_K",
    "Q5_K_M (5-bit K-quant Medium)": "Q5_K_M",
    "Q5_K_S (5-bit K-quant Small)": "Q5_K_S",
    "Q5_1 (5-bit v1)": "Q5_1",
    "Q5_0 (5-bit v0)": "Q5_0",
    "Q4_K_M (4-bit K-quant Medium，推荐)": "Q4_K_M",
    "Q4_K_S (4-bit K-quant Small)": "Q4_K_S",
    "Q4_1 (4-bit v1)": "Q4_1",
    "Q4_0 (4-bit v0)": "Q4_0",
    "Q3_K_L (3-bit K-quant Large)": "Q3_K_L",
    "Q3_K_M (3-bit K-quant Medium)": "Q3_K_M",
    "Q3_K_S (3-bit K-quant Small)": "Q3_K_S",
    "Q2_K (2-bit K-quant)": "Q2_K",
    "IQ4_XS (imatrix 4-bit XS)": "IQ4_XS",
    "IQ4_NL (imatrix 4-bit NL)": "IQ4_NL",
    "IQ3_XS (imatrix 3-bit XS)": "IQ3_XS",
    "IQ3_XXS (imatrix 3-bit XXS)": "IQ3_XXS",
    "IQ2_XXS (imatrix 2-bit XXS)": "IQ2_XXS",
    "IQ2_XS (imatrix 2-bit XS)": "IQ2_XS",
    "IQ2_S (imatrix 2-bit S)": "IQ2_S",
    "IQ1_M (imatrix 1-bit M)": "IQ1_M",
    "BF16 (Brain Float 16)": "BF16",
}


# ============================================================
# 工具函数
# ============================================================
def find_system_python():
    """查找系统 Python3"""
    candidates = [
        "/usr/local/bin/python3",
        "/opt/homebrew/bin/python3",
        "/usr/bin/python3",
        shutil.which("python3"),
    ]
    for c in candidates:
        if c and Path(c).is_file():
            return c
    return None


def get_convert_python():
    """获取用于转换的 Python 路径（优先用系统 Python）"""
    return find_system_python()


def get_subprocess_env():
    """获取子进程的环境变量（确保能 import 内置依赖）"""
    env = os.environ.copy()
    if BUNDLED_DEPS:
        sp = list(BUNDLED_DEPS.glob("lib/python*/site-packages"))
        if sp:
            existing = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = str(sp[0]) + (os.pathsep + existing if existing else "")
    return env


# ============================================================
# 主应用
# ============================================================
class ConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("1100x680")
        self.root.minsize(900, 600)

        self.is_running = False
        self.process = None
        self._msg_queue = queue.Queue()

        self.model_path = tk.StringVar()
        self.llama_cpp_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.quant_type = tk.StringVar(value="Q4_K_M (4-bit K-quant Medium，推荐)")
        self.use_outtype = tk.BooleanVar(value=False)

        self._load_config()
        self._build_ui()
        self._check_status()

    def _load_config(self):
        if CONFIG_FILE.exists():
            try:
                cfg = json.loads(CONFIG_FILE.read_text())
                self.llama_cpp_path.set(cfg.get("llama_cpp_path", ""))
                self.model_path.set(cfg.get("model_path", ""))
                self.output_path.set(cfg.get("output_path", ""))
            except Exception:
                pass
        if not self.llama_cpp_path.get() and DEFAULT_LLAMA_CPP.is_dir():
            self.llama_cpp_path.set(str(DEFAULT_LLAMA_CPP))

    def _save_config(self):
        cfg = {
            "llama_cpp_path": self.llama_cpp_path.get(),
            "model_path": self.model_path.get(),
            "output_path": self.output_path.get(),
        }
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))

    # --------------------------------------------------------
    #  UI
    # --------------------------------------------------------
    def _build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use("aqua")
        except Exception:
            pass
        style.configure("Title.TLabel", font=("Helvetica", 16, "bold"))
        style.configure("Section.TLabelframe.Label", font=("Helvetica", 11, "bold"))
        style.configure("Status.TLabel", font=("Helvetica", 10))
        style.configure("Big.TButton", font=("Helvetica", 13, "bold"), padding=10)

        main = ttk.Frame(self.root, padding=10)
        main.pack(fill=tk.BOTH, expand=True)

        # 标题
        ttk.Label(main, text="SafeTensors → GGUF 转换器", style="Title.TLabel").pack(
            anchor=tk.W, pady=(0, 8)
        )

        # 左右分栏
        pane = ttk.PanedWindow(main, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True)

        # ── 左侧：控件 ──
        left = ttk.Frame(pane, padding=5)
        pane.add(left, weight=3)

        # 状态栏
        fr_status = ttk.Frame(left)
        fr_status.pack(fill=tk.X, pady=(0, 6))
        self.lbl_env = ttk.Label(fr_status, text="检查中…", style="Status.TLabel")
        self.lbl_env.pack(side=tk.LEFT)
        self.lbl_python = ttk.Label(fr_status, text="", foreground="gray")
        self.lbl_python.pack(side=tk.RIGHT)

        # llama.cpp 路径
        fr_llama = ttk.LabelFrame(left, text=" llama.cpp 路径", style="Section.TLabelframe", padding=8)
        fr_llama.pack(fill=tk.X, pady=(0, 6))
        row_llama = ttk.Frame(fr_llama)
        row_llama.pack(fill=tk.X)
        ttk.Entry(row_llama, textvariable=self.llama_cpp_path).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        ttk.Button(row_llama, text="浏览…", command=self._browse_llama_cpp).pack(side=tk.RIGHT)
        # 下载和编译按钮
        row_llama_btn = ttk.Frame(fr_llama)
        row_llama_btn.pack(fill=tk.X, pady=(6, 0))
        self.btn_download = ttk.Button(row_llama_btn, text="⬇ 下载 llama.cpp",
                                       command=self._download_llama_cpp)
        self.btn_download.pack(side=tk.LEFT, padx=(0, 6))
        self.btn_compile = ttk.Button(row_llama_btn, text="⚙ 编译 llama.cpp",
                                      command=self._compile_llama_cpp)
        self.btn_compile.pack(side=tk.LEFT)
        self.lbl_llama_status = ttk.Label(row_llama_btn, text="", foreground="gray")
        self.lbl_llama_status.pack(side=tk.RIGHT)
        ttk.Label(fr_llama, text="首次使用需下载并编译 llama.cpp（需要 cmake）",
                  foreground="gray").pack(anchor=tk.W, pady=(3, 0))

        # 模型目录
        fr_model = ttk.LabelFrame(left, text=" 模型目录 ", style="Section.TLabelframe", padding=8)
        fr_model.pack(fill=tk.X, pady=(0, 6))
        row_model = ttk.Frame(fr_model)
        row_model.pack(fill=tk.X)
        ttk.Entry(row_model, textvariable=self.model_path).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        ttk.Button(row_model, text="浏览…", command=self._browse_model).pack(side=tk.RIGHT)
        ttk.Label(fr_model, text="包含 .safetensors 和 config.json 的文件夹",
                  foreground="gray").pack(anchor=tk.W, pady=(3, 0))

        # 输出目录
        fr_out = ttk.LabelFrame(left, text=" 输出目录 ", style="Section.TLabelframe", padding=8)
        fr_out.pack(fill=tk.X, pady=(0, 6))
        row_out = ttk.Frame(fr_out)
        row_out.pack(fill=tk.X)
        ttk.Entry(row_out, textvariable=self.output_path).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        ttk.Button(row_out, text="浏览…", command=self._browse_output).pack(side=tk.RIGHT)
        ttk.Label(fr_out, text="GGUF 文件输出位置（默认为模型目录）", foreground="gray").pack(anchor=tk.W, pady=(3, 0))

        # 量化设置
        fr_quant = ttk.LabelFrame(left, text=" 量化设置 ", style="Section.TLabelframe", padding=8)
        fr_quant.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(fr_quant, text="量化类型：").pack(anchor=tk.W)
        ttk.Combobox(fr_quant, textvariable=self.quant_type, values=list(QUANT_TYPES.keys()),
                     state="readonly", width=40).pack(fill=tk.X, pady=(4, 4))
        ttk.Checkbutton(fr_quant, text="使用 --outtype（F16/BF16 专用）",
                        variable=self.use_outtype).pack(anchor=tk.W)

        # 操作按钮 + 进度条
        fr_btn = ttk.Frame(left)
        fr_btn.pack(fill=tk.X, pady=(6, 4))
        self.btn_convert = ttk.Button(fr_btn, text="▶  开始转换", style="Big.TButton",
                                      command=self._start_conversion)
        self.btn_convert.pack(side=tk.LEFT, padx=(0, 8))
        self.btn_stop = ttk.Button(fr_btn, text="■  停止", command=self._stop_conversion, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT)
        self.lbl_status = ttk.Label(fr_btn, text="就绪", style="Status.TLabel")
        self.lbl_status.pack(side=tk.RIGHT)

        self.progress_bar = ttk.Progressbar(left, mode="determinate", maximum=100)
        self.progress_bar.pack(fill=tk.X)

        # ── 右侧：日志 ──
        right = ttk.Frame(pane, padding=5)
        pane.add(right, weight=2)

        fr_log = ttk.LabelFrame(right, text=" 输出日志 ", style="Section.TLabelframe", padding=5)
        fr_log.pack(fill=tk.BOTH, expand=True)
        self.log_text = scrolledtext.ScrolledText(fr_log, wrap=tk.WORD, font=("Menlo", 11),
                                                  bg="#1e1e1e", fg="#d4d4d4",
                                                  insertbackground="#d4d4d4",
                                                  selectbackground="#264f78")
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.configure(state=tk.DISABLED)
        self.log_text.tag_configure("info", foreground="#d4d4d4")
        self.log_text.tag_configure("success", foreground="#4ec9b0")
        self.log_text.tag_configure("error", foreground="#f44747")
        self.log_text.tag_configure("warn", foreground="#cca700")
        self.log_text.tag_configure("cmd", foreground="#569cd6")

    # --------------------------------------------------------
    #  状态检查
    # --------------------------------------------------------
    def _check_status(self):
        py = get_convert_python()
        if py:
            self.lbl_env.configure(text="✓ 运行环境就绪", foreground="#4ec9b0")
            self.lbl_python.configure(text=f"Python: {py}")
        else:
            self.lbl_env.configure(text="✗ 未找到 Python3", foreground="#f44747")

    # --------------------------------------------------------
    #  文件浏览
    # --------------------------------------------------------
    def _browse_llama_cpp(self):
        d = filedialog.askdirectory(title="选择 llama.cpp 根目录")
        if d:
            self.llama_cpp_path.set(d)
            self._save_config()

    def _browse_model(self):
        d = filedialog.askdirectory(title="选择模型目录（含 .safetensors 文件）")
        if d:
            self.model_path.set(d)
            if not self.output_path.get():
                self.output_path.set(d)
            self._save_config()

    def _browse_output(self):
        d = filedialog.askdirectory(title="选择输出目录")
        if d:
            self.output_path.set(d)
            self._save_config()

    # --------------------------------------------------------
    #  llama.cpp 下载 & 编译
    # --------------------------------------------------------
    def _set_llama_status(self, text, color="gray"):
        self.lbl_llama_status.configure(text=text, foreground=color)

    def _download_llama_cpp(self):
        """下载 llama.cpp 到 ~/Downloads/llama.cpp"""
        dest = Path.home() / "Downloads" / "llama.cpp"
        if dest.exists() and (dest / "convert_hf_to_gguf.py").exists():
            if not messagebox.askyesno("确认", f"llama.cpp 已存在于:\n{dest}\n\n是否删除重新下载？"):
                return
            shutil.rmtree(dest)

        self.btn_download.configure(state=tk.DISABLED)
        self.btn_compile.configure(state=tk.DISABLED)
        self._set_llama_status("下载中…", "#cca700")
        self.is_running = True
        threading.Thread(target=self._run_download, args=(dest,), daemon=True).start()

    def _run_download(self, dest: Path):
        Q = self._qput
        log = lambda msg, tag="info": Q(self._log, msg, tag)

        log("=" * 60)
        log("开始下载 llama.cpp…")
        log(f"目标目录: {dest}")

        # 尝试 git clone
        git_bin = shutil.which("git")
        if git_bin:
            log("使用 git clone…")
            cmd = [git_bin, "clone", "--depth", "1",
                   "https://github.com/ggerganov/llama.cpp.git", str(dest)]
            try:
                self.process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1,
                )
                for line in self.process.stdout:
                    line = line.rstrip()
                    if line:
                        log(line)
                self.process.wait()

                if self.process.returncode == 0:
                    log("✓ 下载完成！", "success")
                    Q(self.llama_cpp_path.set, str(dest))
                    Q(self._save_config)
                    Q(self._set_llama_status, "下载完成", "#4ec9b0")
                else:
                    log(f"git clone 失败 (退出码: {self.process.returncode})", "error")
                    Q(self._set_llama_status, "下载失败", "#f44747")
            except Exception as e:
                log(f"下载异常: {e}", "error")
                Q(self._set_llama_status, "下载失败", "#f44747")
        else:
            log("未找到 git，请先安装 git 或手动下载 llama.cpp", "error")
            Q(self._set_llama_status, "需要 git", "#f44747")

        Q(self.btn_download.configure, {"state": tk.NORMAL})
        Q(self.btn_compile.configure, {"state": tk.NORMAL})
        self.is_running = False

    def _compile_llama_cpp(self):
        """编译 llama.cpp"""
        llama_dir = Path(self.llama_cpp_path.get())
        if not llama_dir.is_dir():
            messagebox.showerror("错误", "请先设置有效的 llama.cpp 目录")
            return
        if not (llama_dir / "CMakeLists.txt").exists():
            messagebox.showerror("错误", f"llama.cpp 目录中未找到 CMakeLists.txt:\n{llama_dir}")
            return

        self.btn_download.configure(state=tk.DISABLED)
        self.btn_compile.configure(state=tk.DISABLED)
        self._set_llama_status("编译中…", "#cca700")
        self.is_running = True
        threading.Thread(target=self._run_compile, args=(llama_dir,), daemon=True).start()

    def _run_compile(self, llama_dir: Path):
        Q = self._qput
        log = lambda msg, tag="info": Q(self._log, msg, tag)

        log("=" * 60)
        log("开始编译 llama.cpp…")
        log(f"源码目录: {llama_dir}")

        # 找 cmake（优先 pip 安装的 cmake）
        cmake_bin = shutil.which("cmake")
        pip_cmake = Path(sys.prefix) / "bin" / "cmake"
        if not cmake_bin and pip_cmake.exists():
            cmake_bin = str(pip_cmake)
        # 也检查 python3 -m cmake
        if not cmake_bin:
            try:
                subprocess.run([sys.executable, "-m", "cmake", "--version"],
                               capture_output=True, check=True)
                cmake_bin = f"{sys.executable} -m cmake"
            except Exception:
                pass

        if not cmake_bin:
            log("未找到 cmake，请先安装: pip install cmake", "error")
            Q(self._set_llama_status, "需要 cmake", "#f44747")
            Q(self.btn_download.configure, {"state": tk.NORMAL})
            Q(self.btn_compile.configure, {"state": tk.NORMAL})
            self.is_running = False
            return

        # Step 1: cmake configure
        log(f"\n步骤 1: cmake 配置…")
        log(f"cmake: {cmake_bin}")
        use_python_cmake = "python" in cmake_bin
        if use_python_cmake:
            cmd1 = [sys.executable, "-m", "cmake", "-B", "build",
                    "-DCMAKE_BUILD_TYPE=Release"]
        else:
            cmd1 = [cmake_bin, "-B", "build", "-DCMAKE_BUILD_TYPE=Release"]

        try:
            self.process = subprocess.Popen(
                cmd1, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, cwd=str(llama_dir),
            )
            for line in self.process.stdout:
                if not self.is_running:
                    break
                line = line.rstrip()
                if line:
                    tag = "error" if "error" in line.lower() else "info"
                    log(line, tag)
            self.process.wait()

            if self.process.returncode != 0:
                log(f"cmake 配置失败 (退出码: {self.process.returncode})", "error")
                Q(self._set_llama_status, "编译失败", "#f44747")
                Q(self.btn_download.configure, {"state": tk.NORMAL})
                Q(self.btn_compile.configure, {"state": tk.NORMAL})
                self.is_running = False
                return

            log("✓ cmake 配置完成", "success")
        except Exception as e:
            log(f"cmake 配置异常: {e}", "error")
            Q(self._set_llama_status, "编译失败", "#f44747")
            Q(self.btn_download.configure, {"state": tk.NORMAL})
            Q(self.btn_compile.configure, {"state": tk.NORMAL})
            self.is_running = False
            return

        # Step 2: cmake build
        log(f"\n步骤 2: cmake 编译…")
        if use_python_cmake:
            cmd2 = [sys.executable, "-m", "cmake", "--build", "build",
                    "--config", "Release"]
        else:
            cmd2 = [cmake_bin, "--build", "build", "--config", "Release"]

        try:
            self.process = subprocess.Popen(
                cmd2, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, cwd=str(llama_dir),
            )
            for line in self.process.stdout:
                if not self.is_running:
                    break
                line = line.rstrip()
                if line:
                    log(line)
            self.process.wait()

            if self.process.returncode != 0:
                log(f"编译失败 (退出码: {self.process.returncode})", "error")
                Q(self._set_llama_status, "编译失败", "#f44747")
            else:
                # 检查产物
                quantize_bin = llama_dir / "build" / "bin" / "llama-quantize"
                convert_py = llama_dir / "convert_hf_to_gguf.py"
                ok = True
                if not quantize_bin.exists():
                    # 尝试 Release 子目录
                    quantize_bin = llama_dir / "build" / "bin" / "Release" / "llama-quantize"
                if not convert_py.exists():
                    log("⚠ 未找到 convert_hf_to_gguf.py（可能在不同分支）", "warn")
                if quantize_bin.exists():
                    log(f"✓ llama-quantize: {quantize_bin}", "success")
                else:
                    log("⚠ 未找到 llama-quantize", "warn")
                    ok = False
                if ok:
                    log("\n✓ 编译完成！", "success")
                    Q(self._set_llama_status, "编译完成", "#4ec9b0")
                else:
                    Q(self._set_llama_status, "编译完成（部分缺失）", "#cca700")
        except Exception as e:
            log(f"编译异常: {e}", "error")
            Q(self._set_llama_status, "编译失败", "#f44747")

        Q(self.btn_download.configure, {"state": tk.NORMAL})
        Q(self.btn_compile.configure, {"state": tk.NORMAL})
        self.is_running = False

    # --------------------------------------------------------
    #  日志 & 队列
    # --------------------------------------------------------
    def _log(self, msg, tag="info"):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, f"[{ts}] {msg}\n", tag)
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _qput(self, func, *args):
        self._msg_queue.put((func, args))

    def _poll_queue(self):
        try:
            while True:
                func, args = self._msg_queue.get_nowait()
                func(*args)
        except queue.Empty:
            pass
        if self.is_running or not self._msg_queue.empty():
            self.root.after(100, self._poll_queue)

    # --------------------------------------------------------
    #  转换
    # --------------------------------------------------------
    def _validate_inputs(self):
        py = get_convert_python()
        if not py:
            messagebox.showerror("错误", "未找到 Python3 环境")
            return False

        llama = self.llama_cpp_path.get()
        if not llama or not Path(llama).is_dir():
            messagebox.showerror("错误", "请选择有效的 llama.cpp 目录")
            return False
        if not (Path(llama) / "convert_hf_to_gguf.py").exists():
            messagebox.showerror("错误", f"llama.cpp 目录中未找到 convert_hf_to_gguf.py:\n{llama}")
            return False

        model = self.model_path.get()
        if not model or not Path(model).is_dir():
            messagebox.showerror("错误", "请选择有效的模型目录")
            return False
        if not list(Path(model).glob("*.safetensors")):
            messagebox.showerror("错误", f"模型目录中未找到 .safetensors 文件:\n{model}")
            return False
        if not (Path(model) / "config.json").exists():
            if not messagebox.askyesno("警告", "模型目录中未找到 config.json，转换可能失败。\n是否继续？"):
                return False

        if not self.output_path.get():
            self.output_path.set(model)
        self._save_config()
        return True

    def _start_conversion(self):
        if not self._validate_inputs():
            return
        self.is_running = True
        self.btn_convert.configure(state=tk.DISABLED)
        self.btn_stop.configure(state=tk.NORMAL)
        self.progress_bar["value"] = 0
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)
        self.root.after(100, self._poll_queue)
        threading.Thread(target=self._run_conversion, daemon=True).start()

    def _stop_conversion(self):
        self.is_running = False
        if self.process:
            try:
                self.process.terminate()
            except Exception:
                pass
        self._log("用户取消操作", "warn")
        self._finish("已停止")

    def _finish(self, status="就绪"):
        self.is_running = False
        self.process = None
        self.btn_convert.configure(state=tk.NORMAL)
        self.btn_stop.configure(state=tk.DISABLED)
        self.lbl_status.configure(text=status)

    def _find_quantize_binary(self, llama_dir):
        search_dirs = [
            llama_dir / "build" / "bin",
            llama_dir / "build" / "bin" / "Release",
            llama_dir / "build" / "bin" / "Debug",
            llama_dir,
        ]
        for d in search_dirs:
            for name in ["llama-quantize", "quantize"]:
                p = d / name
                if p.exists():
                    return str(p)
        return None

    # ── Llama 3 标准 chat template ──
    LLAMA3_CHAT_TEMPLATE = (
        "{% set loop_messages = messages %}"
        "{% for message in loop_messages %}"
        "{% set content = '<|start_header_id|>' + message['role'] + '<|end_header_id|>\n\n'"
        "+ message['content'] | trim + '<|eot_id|>' %}"
        "{% if loop.index0 == 0 %}{% set content = bos_token + content %}{% endif %}"
        "{{ content }}"
        "{% endfor %}"
        "{% if add_generation_prompt %}"
        "{{ '<|start_header_id|>assistant<|end_header_id|>\n\n' }}"
        "{% endif %}"
    )

    def _inject_chat_template_if_needed(self, model_dir: Path, log) -> bool:
        """检查模型是否缺少 chat template，如果是 Llama 3 模型则自动注入。返回是否注入了临时文件。"""
        # 检查是否已有 chat template
        has_template = False
        config_path = model_dir / "tokenizer_config.json"
        if config_path.exists():
            try:
                cfg = json.loads(config_path.read_text())
                if cfg.get("chat_template"):
                    has_template = True
            except Exception:
                pass
        if (model_dir / "chat_template.jinja").exists():
            has_template = True
        if (model_dir / "chat_template.json").exists():
            has_template = True

        if has_template:
            log("✓ 模型已包含 chat template", "info")
            return False

        # 检测是否为 Llama 3 架构
        is_llama3 = False
        if config_path.exists():
            try:
                cfg = json.loads(config_path.read_text())
                model_type = cfg.get("model_type", "")
                vocab_size = cfg.get("vocab_size", 0)
                if model_type in ("llama",) and vocab_size == 128256:
                    is_llama3 = True
            except Exception:
                pass

        if not is_llama3:
            log("⚠ 模型缺少 chat template，但非 Llama 3 架构，跳过自动注入", "warn")
            return False

        # 注入 Llama 3 标准 chat template
        template_path = model_dir / "chat_template.jinja"
        template_path.write_text(self.LLAMA3_CHAT_TEMPLATE)
        log("✓ 检测到 Llama 3 模型缺少 chat template，已自动注入标准模板", "success")
        log("  → 已创建临时文件: chat_template.jinja", "info")
        return True

    def _run_conversion(self):
        llama_dir = Path(self.llama_cpp_path.get())
        model_dir = Path(self.model_path.get())
        out_dir = Path(self.output_path.get()) or model_dir

        venv_python = get_convert_python()
        convert_script = llama_dir / "convert_hf_to_gguf.py"
        quantize_bin = self._find_quantize_binary(llama_dir)

        quant_label = self.quant_type.get()
        quant_code = QUANT_TYPES[quant_label]
        use_outtype = self.use_outtype.get()
        env = get_subprocess_env()

        out_dir.mkdir(parents=True, exist_ok=True)
        model_name = model_dir.name
        total_steps = 2 if quant_code not in ("F16", "BF16") else 1

        Q = self._qput

        def log(msg, tag="info"):
            Q(self._log, msg, tag)

        def status(msg, step=0):
            pct = int(step / total_steps * 100) if total_steps else 100
            Q(self.lbl_status.configure, {"text": msg})
            Q(self.progress_bar.configure, {"value": pct})

        log("=" * 60)
        log(f"模型目录: {model_dir}")
        log(f"llama.cpp: {llama_dir}")
        log(f"输出目录: {out_dir}")
        log(f"量化类型: {quant_label} ({quant_code})")
        log(f"Python: {venv_python}")
        log("=" * 60)

        # ── 检查并注入 chat template ──
        injected_template = self._inject_chat_template_if_needed(model_dir, log)

        # ── 步骤 1: 转换 GGUF (F16) ──
        status("步骤 1/2: 转换格式中…", 0)
        log("步骤 1: 将 SafeTensors 转换为 GGUF (F16)…")

        f16_output = out_dir / f"{model_name}-f16.gguf"
        cmd = [venv_python, str(convert_script), str(model_dir), "--outfile", str(f16_output), "--special"]
        if use_outtype and quant_code in ("F16", "BF16"):
            cmd.extend(["--outtype", quant_code.lower()])
        log(f"执行: {' '.join(cmd)}", "cmd")

        try:
            self.process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, cwd=str(llama_dir), env=env,
            )
            for line in self.process.stdout:
                if not self.is_running:
                    break
                line = line.rstrip()
                if line:
                    tag = "error" if "error" in line.lower() else ("warn" if "warn" in line.lower() else "info")
                    log(line, tag)
            self.process.wait()

            if not self.is_running:
                Q(self._finish, "已停止")
                return
            if self.process.returncode != 0:
                log(f"转换失败 (退出码: {self.process.returncode})", "error")
                Q(self._finish, "转换失败")
                return
            if not f16_output.exists():
                log(f"输出文件未生成: {f16_output}", "error")
                Q(self._finish, "转换失败")
                return

            f16_size = f16_output.stat().st_size / (1024 ** 3)
            log(f"✓ F16 GGUF: {f16_output.name} ({f16_size:.2f} GB)", "success")
            status("步骤 1/2: 转换完成", 1)

        except Exception as e:
            log(f"转换异常: {e}", "error")
            Q(self._finish, "转换失败")
            return
        finally:
            # 清理临时注入的 chat template
            if injected_template:
                try:
                    (model_dir / "chat_template.jinja").unlink(missing_ok=True)
                    log("已清理临时 chat template 文件", "info")
                except Exception:
                    pass

        # ── 步骤 2: 量化 ──
        if quant_code in ("F16", "BF16"):
            log("无量化类型，跳过量化步骤", "success")
            log(f"\n{'=' * 60}", "success")
            log(f"✓ 转换完成！输出: {f16_output}", "success")
            log(f"{'=' * 60}", "success")
            Q(self._finish, "转换完成")
            return

        if not quantize_bin:
            log("未找到 llama-quantize，请先编译 llama.cpp:", "error")
            log("  cd llama.cpp && cmake -B build && cmake --build build", "cmd")
            log(f"\nF16 GGUF 已生成: {f16_output}", "warn")
            Q(self._finish, "需手动量化")
            return

        status(f"步骤 2/2: 量化为 {quant_code}…", 1)
        log(f"\n步骤 2: 量化为 {quant_code}…")

        quant_output = out_dir / f"{model_name}-{quant_code}.gguf"
        cmd2 = [quantize_bin, str(f16_output), str(quant_output), quant_code]
        log(f"执行: {' '.join(cmd2)}", "cmd")

        try:
            self.process = subprocess.Popen(
                cmd2, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, env=env,
            )
            for line in self.process.stdout:
                if not self.is_running:
                    break
                line = line.rstrip()
                if line:
                    log(line, "info")
            self.process.wait()

            if not self.is_running:
                Q(self._finish, "已停止")
                return
            if self.process.returncode != 0:
                log(f"量化失败 (退出码: {self.process.returncode})", "error")
                log(f"F16 GGUF 仍然可用: {f16_output}", "warn")
                Q(self._finish, "量化失败")
                return
            if not quant_output.exists():
                log(f"量化输出未生成: {quant_output}", "error")
                Q(self._finish, "量化失败")
                return

            quant_size = quant_output.stat().st_size / (1024 ** 3)
            log(f"✓ 量化完成: {quant_output.name} ({quant_size:.2f} GB)", "success")

        except Exception as e:
            log(f"量化异常: {e}", "error")
            Q(self._finish, "量化失败")
            return

        Q(self.progress_bar.configure, {"value": 100})
        log(f"\n{'=' * 60}", "success")
        log("✓ 全部完成！", "success")
        log(f"  输出: {quant_output}", "success")
        log(f"  大小: {quant_size:.2f} GB", "success")
        if f16_size > 0:
            log(f"  压缩: {quant_size / f16_size * 100:.1f}% (F16: {f16_size:.2f} GB)", "success")
        log(f"{'=' * 60}", "success")
        Q(self._finish, "转换完成")


def main():
    root = tk.Tk()
    ConverterApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
