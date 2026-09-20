"""「一箭又一箭」游戏入口。

运行：
    python main.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# 允许从任意目录运行本文件：把项目根目录放进模块搜索路径
sys.path.insert(0, str(Path(__file__).resolve().parent))

# 关掉 pygame 导入时打印的社区欢迎语，保持控制台输出干净
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

# Windows 控制台默认 GBK，中文提示会变成乱码
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main() -> int:
    try:
        import pygame  # noqa: F401
    except ImportError:
        print("缺少 pygame，请先安装依赖：")
        print("    python -m pip install -r requirements.txt")
        return 1

    from game.scenes import App

    App().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
