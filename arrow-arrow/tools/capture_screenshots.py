"""把游戏的各个界面渲染成 PNG，供 README 和博客使用。

用 SDL 的 dummy 视频驱动在内存里开窗口，不需要真的弹出界面，
因此可以在无人值守的情况下批量出图，改过界面后重跑一次即可更新。

用法：
    python tools/capture_screenshots.py
    python tools/capture_screenshots.py --out docs/images
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pygame  # noqa: E402

from game.board import GameState  # noqa: E402
from game.scenes import App, PlayScene, ResultScene  # noqa: E402


class Capturer:
    """负责推进帧、截图、以及把游戏驱到指定状态。"""

    def __init__(self, out_dir: Path) -> None:
        self.out_dir = out_dir
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.app = App()

    def save(self, name: str, frames: int = 3) -> None:
        for _ in range(frames):
            self.app.scene.update(1 / 60)
            self.app.scene.draw(self.app.screen)
        path = self.out_dir / name
        pygame.image.save(self.app.screen, str(path))
        print(f"  已保存 {path.relative_to(ROOT)}")

    def pump(self, frames: int = 1) -> None:
        for _ in range(frames):
            self.app.scene.update(1 / 60)
            self.app.scene.draw(self.app.screen)

    def advance_until_result(self, limit: int = 240) -> None:
        for _ in range(limit):
            if not isinstance(self.app.scene, PlayScene):
                return
            self.pump(1)

    def play_through(self, level_index: int, wrong_clicks: int = 0) -> None:
        """用贪心顺序把某一关打完；``wrong_clicks`` 用来故意制造失误。"""
        self.app.start_level(level_index)
        play = self.app.scene
        assert isinstance(play, PlayScene)

        for _ in range(wrong_clicks):
            blocked = [a for a in play.board.arrows.values() if not play.board.is_free(a)]
            if not blocked:
                break
            play._click_cell(blocked[0].row, blocked[0].col)
            self.pump(3)

        guard = 0
        while isinstance(self.app.scene, PlayScene) and guard < 300:
            play = self.app.scene
            if play.board.state is not GameState.PLAYING:
                break
            free = play.board.free_arrows()
            if not free:
                break
            play._click_cell(free[0].row, free[0].col)
            self.pump(4)
            guard += 1

        self.advance_until_result()


def main() -> int:
    parser = argparse.ArgumentParser(description="渲染游戏界面截图")
    parser.add_argument(
        "--out",
        default=str(ROOT / "screenshots"),
        help="输出目录，默认 screenshots/",
    )
    args = parser.parse_args()

    cap = Capturer(Path(args.out))
    print("开始渲染截图……")

    # 1. 开始界面
    cap.save("01-开始界面.png")

    # 2. 游戏界面（第一关）
    cap.app.start_level(0)
    cap.save("02-游戏界面-第一关.png")

    # 3. 游戏界面（第五关，6x6 大棋盘）
    cap.app.start_level(4)
    cap.save("03-游戏界面-第五关.png")

    # 4. 碰撞反馈：点击一个被挡住的箭头，抖动 + 高亮 + 提示条
    cap.app.start_level(0)
    play = cap.app.scene
    blocked = [a for a in play.board.arrows.values() if not play.board.is_free(a)]
    if blocked:
        play._click_cell(blocked[0].row, blocked[0].col)
        cap.save("04-碰撞反馈.png", frames=5)

    # 5. 提示功能
    cap.app.start_level(2)
    cap.app.scene.use_hint()
    cap.save("05-提示功能.png", frames=8)

    # 6. 通关界面
    cap.play_through(0)
    cap.save("06-通关界面.png", frames=2)
    assert isinstance(cap.app.scene, ResultScene)

    # 7. 失败界面
    cap.app.start_level(1)
    play = cap.app.scene
    guard = 0
    while play.board.state is GameState.PLAYING and guard < 60:
        blocked = [a for a in play.board.arrows.values() if not play.board.is_free(a)]
        if not blocked:
            break
        play._click_cell(blocked[0].row, blocked[0].col)
        cap.pump(2)
        guard += 1
    cap.advance_until_result()
    cap.save("07-失败界面.png", frames=2)

    pygame.quit()
    print("完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
