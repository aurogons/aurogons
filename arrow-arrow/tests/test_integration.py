"""无头集成测试：把整个游戏真正跑起来。

棋盘逻辑的单测（test_board.py）验证不了场景切换、动画、按钮这些东西。
这里用 SDL 的 dummy 视频驱动把窗口开在内存里，不需要显示器，
就能把「点击 -> 消除 -> 通关 -> 进入下一关」这条完整链路走一遍。

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import os
import unittest

# 必须在导入 pygame 之前设置：让 SDL 用一个不真正开窗口的视频驱动
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

from game.board import GameState  # noqa: E402
from game.levels import LEVELS  # noqa: E402
from game.scenes import App, PlayScene, ResultScene, StartScene  # noqa: E402


def setUpModule() -> None:
    pygame.init()


def tearDownModule() -> None:
    pygame.quit()


class GameTestBase(unittest.TestCase):
    """提供推进帧与模拟点击的公共工具。"""

    def setUp(self) -> None:
        self.app = App()

    def pump(self, frames: int = 4) -> None:
        """推进若干帧，让动画和计时器往前走。"""
        for _ in range(frames):
            self.app.scene.update(1 / 60)
            self.app.scene.draw(self.app.screen)

    def click_cell(self, play: PlayScene, row: int, col: int) -> None:
        """按真实鼠标事件路径点击某个格子（而不是直接调内部方法）。"""
        pos = play.cell_rect(row, col).center
        play.handle_event(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos)
        )

    def play_level_to_end(self, level_index: int) -> ResultScene:
        """用贪心顺序把某一关打完，返回结算场景。"""
        self.app.start_level(level_index)

        guard = 0
        while isinstance(self.app.scene, PlayScene) and guard < 500:
            play = self.app.scene
            if play.board.state is not GameState.PLAYING:
                self.pump(1)
                guard += 1
                continue

            free = play.board.free_arrows()
            self.assertTrue(free, "局面卡死了，正常关卡不该出现")
            target = free[0]
            self.click_cell(play, target.row, target.col)
            self.pump(4)
            guard += 1

        self.assertIsInstance(self.app.scene, ResultScene)
        return self.app.scene


class TestSceneFlow(GameTestBase):
    """场景切换。"""

    def test_启动进入开始界面(self) -> None:
        self.assertIsInstance(self.app.scene, StartScene)
        self.pump()

    def test_开始游戏进入关卡(self) -> None:
        self.app.start_new_game()
        self.assertIsInstance(self.app.scene, PlayScene)

    def test_从开始界面进入指定关卡(self) -> None:
        self.app.start_level(2)
        self.assertIsInstance(self.app.scene, PlayScene)
        self.assertEqual(self.app.scene.level_index, 2)

    def test_三个场景都能正常绘制(self) -> None:
        self.pump()                                   # 开始界面
        self.app.start_level(0)
        self.pump()                                   # 游戏界面
        result = self.play_level_to_end(0)
        self.pump()                                   # 结算界面
        self.assertIsInstance(result, ResultScene)


class TestWinFlow(GameTestBase):
    """通关链路（对应测试 T04）。"""

    def test_打完第一关进入通关结算(self) -> None:
        result = self.play_level_to_end(0)
        self.assertTrue(result.won)
        self.assertEqual(result.play.board.remaining, 0)

    def test_通关不消耗失误次数(self) -> None:
        result = self.play_level_to_end(0)
        self.assertEqual(result.play.board.misses_left, result.play.board.max_misses)

    def test_通关后解锁下一关(self) -> None:
        self.assertEqual(self.app.unlocked, 1)
        self.play_level_to_end(0)
        self.assertEqual(self.app.unlocked, 2)

    def test_逐关通关直到最后一关(self) -> None:
        for index in range(len(LEVELS)):
            with self.subTest(level=LEVELS[index].name):
                result = self.play_level_to_end(index)
                self.assertTrue(result.won)
        self.assertEqual(self.app.unlocked, len(LEVELS))

    def test_下一关按钮切到下一关(self) -> None:
        result = self.play_level_to_end(0)
        result._next_level()
        self.assertIsInstance(self.app.scene, PlayScene)
        self.assertEqual(self.app.scene.level_index, 1)

    def test_重玩本关按钮回到同一关(self) -> None:
        result = self.play_level_to_end(1)
        result._replay()
        self.assertIsInstance(self.app.scene, PlayScene)
        self.assertEqual(self.app.scene.level_index, 1)

    def test_通关界面能返回主菜单(self) -> None:
        result = self.play_level_to_end(0)
        result.app.go_start()
        self.assertIsInstance(self.app.scene, StartScene)


class TestLoseFlow(GameTestBase):
    """失败链路（对应测试 T05）。"""

    def _burn_all_misses(self, play: PlayScene) -> None:
        guard = 0
        while play.board.state is GameState.PLAYING and guard < 50:
            blocked = [a for a in play.board.arrows.values() if not play.board.is_free(a)]
            if not blocked:
                break
            self.click_cell(play, blocked[0].row, blocked[0].col)
            self.pump(1)
            guard += 1

    def test_失误耗尽进入失败结算(self) -> None:
        self.app.start_level(0)
        play = self.app.scene
        self._burn_all_misses(play)
        self.assertIs(play.board.state, GameState.LOSE)

        self.pump(90)          # 等失败结算的延迟结束
        self.assertIsInstance(self.app.scene, ResultScene)
        self.assertFalse(self.app.scene.won)

    def test_失败不会解锁下一关(self) -> None:
        self.app.start_level(0)
        self._burn_all_misses(self.app.scene)
        self.pump(90)
        self.assertEqual(self.app.unlocked, 1)

    def test_失败后可以重玩并恢复正常状态(self) -> None:
        self.app.start_level(0)
        play = self.app.scene
        max_misses = play.board.max_misses
        total = play.board.total_arrows

        self._burn_all_misses(play)
        self.pump(90)
        self.app.scene._replay()

        play = self.app.scene
        self.assertIs(play.board.state, GameState.PLAYING)
        self.assertEqual(play.board.remaining, total)
        self.assertEqual(play.board.misses_left, max_misses)


class TestFeedback(GameTestBase):
    """飞出与碰撞反馈。"""

    def test_点击无阻挡的箭头产生飞出动画(self) -> None:
        self.app.start_level(0)
        play = self.app.scene
        free = play.board.free_arrows()[0]

        self.click_cell(play, free.row, free.col)
        self.assertEqual(len(play.flying), 1)
        self.assertNotIn(free.cell, play.board.arrows)
        self.pump(120)
        self.assertEqual(play.flying, [])

    def test_点击有阻挡的箭头产生抖动与高亮(self) -> None:
        self.app.start_level(0)
        play = self.app.scene
        blocked = [a for a in play.board.arrows.values() if not play.board.is_free(a)][0]
        before = play.board.misses_left

        self.click_cell(play, blocked.row, blocked.col)

        self.assertIn(blocked.cell, play.shaking)
        self.assertTrue(play.highlights)
        self.assertIsNotNone(play.toast)
        self.assertEqual(play.board.misses_left, before - 1)
        self.pump(120)
        self.assertEqual(play.shaking, {})

    def test_点击空格没有任何反应(self) -> None:
        self.app.start_level(0)
        play = self.app.scene
        before = play.board.misses_left

        empty = next(
            (r, c)
            for r in range(play.board.rows)
            for c in range(play.board.cols)
            if (r, c) not in play.board.arrows
        )
        self.click_cell(play, *empty)
        self.pump(1)

        self.assertEqual(play.board.misses_left, before)
        self.assertEqual(play.flying, [])
        self.assertEqual(play.shaking, {})


class TestRestartAndUndo(GameTestBase):
    """重新开始（T06）与撤销。"""

    def test_重开按钮恢复本关初始状态(self) -> None:
        self.app.start_level(0)
        play = self.app.scene
        total = play.board.total_arrows
        max_misses = play.board.max_misses

        self.click_cell(play, *play.board.free_arrows()[0].cell)
        blocked = [a for a in play.board.arrows.values() if not play.board.is_free(a)]
        if blocked:
            self.click_cell(play, blocked[0].row, blocked[0].col)
        self.pump(2)

        play.restart()

        self.assertEqual(play.board.remaining, total)
        self.assertEqual(play.board.misses_left, max_misses)
        self.assertEqual(play.play_time, 0.0)
        self.assertEqual(play.history, [])

    def test_撤销恢复上一步(self) -> None:
        self.app.start_level(0)
        play = self.app.scene
        total = play.board.total_arrows
        max_misses = play.board.max_misses

        blocked = [a for a in play.board.arrows.values() if not play.board.is_free(a)][0]
        self.click_cell(play, blocked.row, blocked.col)
        self.assertEqual(play.board.misses_left, max_misses - 1)

        play.undo()

        self.assertEqual(play.board.misses_left, max_misses)
        self.assertEqual(play.board.remaining, total)
        self.assertEqual(play.history, [])

    def test_没有可撤销的操作时撤销无副作用(self) -> None:
        self.app.start_level(0)
        play = self.app.scene
        play.undo()
        self.assertEqual(play.board.remaining, play.board.total_arrows)
        self.assertEqual(play.board.misses_left, play.board.max_misses)

    def test_撤销可以退掉飞出的一步(self) -> None:
        self.app.start_level(0)
        play = self.app.scene
        free = play.board.free_arrows()[0]
        self.click_cell(play, free.row, free.col)
        self.assertNotIn(free.cell, play.board.arrows)

        play.undo()
        self.assertIn(free.cell, play.board.arrows)


class TestHint(GameTestBase):
    """提示功能。"""

    def test_提示给出一个可飞出的箭头(self) -> None:
        self.app.start_level(2)
        play = self.app.scene
        free_cells = {a.cell for a in play.board.free_arrows()}

        play.use_hint()
        self.pump(1)

        self.assertTrue(play.highlights)
        self.assertIsNotNone(play.toast)
        # 提示文字里应当出现某个确实能飞出的格子（坐标从 1 开始数）
        mentioned = {
            (r, c)
            for r in range(play.board.rows)
            for c in range(play.board.cols)
            if f"({r + 1},{c + 1})" in play.toast.text
        }
        self.assertTrue(mentioned & free_cells, f"提示了不能飞的箭头：{play.toast.text}")

    def test_连续提示会轮换目标(self) -> None:
        self.app.start_level(2)
        play = self.app.scene
        if len(play.board.free_arrows()) < 2:
            self.skipTest("本关初始可飞出箭头不足两个")

        play.use_hint()
        first = play.toast.text
        play.use_hint()
        second = play.toast.text
        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main(verbosity=2)
