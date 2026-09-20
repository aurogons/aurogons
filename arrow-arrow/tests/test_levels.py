"""关卡数据的测试。

关卡最容易出的问题不是「代码写错了」，而是「布局摆错了」：
随手改一个箭头就可能摆出一个无论怎么点都通不了的死局。
这些测试把「每关都必须能通关」变成一条断言，以后改关卡数据时
只要跑一遍测试就能发现问题，不用靠人肉试玩。
"""

from __future__ import annotations

import unittest

from game.board import Board, Direction, GameState
from game.levels import LEVELS, build_board, parse_art
from tools.validate_levels import find_mutual_blocks, solve


class TestLevelData(unittest.TestCase):
    """关卡数据自身的合法性。"""

    def test_至少三个关卡(self) -> None:
        """作业要求至少 3 个可以正常通关的关卡。"""
        self.assertGreaterEqual(len(LEVELS), 3)

    def test_关卡名字不重复(self) -> None:
        names = [level.name for level in LEVELS]
        self.assertEqual(len(names), len(set(names)))

    def test_每关都能构造出棋盘(self) -> None:
        for level in LEVELS:
            with self.subTest(level=level.name):
                board = build_board(level)
                self.assertGreater(board.total_arrows, 0)

    def test_每关失误上限为正(self) -> None:
        for level in LEVELS:
            with self.subTest(level=level.name):
                self.assertGreater(level.max_misses, 0)


class TestLevelSolvable(unittest.TestCase):
    """每关都必须存在通关顺序。"""

    def test_全部关卡可通关(self) -> None:
        for level in LEVELS:
            with self.subTest(level=level.name):
                board = build_board(level)
                result = solve(board)
                stuck = [(a.row, a.col) for a in result.stuck]
                self.assertTrue(
                    result.solved,
                    f"{level.name} 无法通关，卡住的箭头：{stuck}",
                )

    def test_贪心解法正好清空全部箭头(self) -> None:
        for level in LEVELS:
            with self.subTest(level=level.name):
                board = build_board(level)
                result = solve(board)
                self.assertEqual(len(result.order), board.total_arrows)
                self.assertEqual(board.remaining, 0)
                self.assertIs(board.state, GameState.WIN)

    def test_没有互相阻挡的箭头对(self) -> None:
        """正面相对的一对箭头必定死锁，是最常见的摆关错误。"""
        for level in LEVELS:
            with self.subTest(level=level.name):
                pairs = find_mutual_blocks(build_board(level))
                detail = [
                    f"({a.row},{a.col}){a.direction.char} <-> "
                    f"({b.row},{b.col}){b.direction.char}"
                    for a, b in pairs
                ]
                self.assertEqual(pairs, [], f"{level.name} 存在互相阻挡：{detail}")

    def test_开局至少有一个箭头能飞出(self) -> None:
        """开局就全军被堵死的关卡，玩家第一步就无从下手。"""
        for level in LEVELS:
            with self.subTest(level=level.name):
                board = build_board(level)
                self.assertGreater(
                    len(board.free_arrows()), 0, f"{level.name} 开局没有任何可选项"
                )

    def test_无失误即可通关(self) -> None:
        """只要按贪心顺序点，一次失误都不需要 —— 关卡不能设计成必须试错。"""
        for level in LEVELS:
            with self.subTest(level=level.name):
                board = build_board(level)
                solve(board)
                self.assertEqual(board.misses_left, board.max_misses)


class TestLevelDifficulty(unittest.TestCase):
    """难度应当随关卡序号递增。"""

    def test_箭头数量不减少(self) -> None:
        counts = [build_board(level).total_arrows for level in LEVELS]
        for previous, current in zip(counts, counts[1:]):
            self.assertLessEqual(previous, current, f"箭头数量曲线：{counts}")

    def test_棋盘尺寸不缩小(self) -> None:
        sizes = [(build_board(l).rows, build_board(l).cols) for l in LEVELS]
        for previous, current in zip(sizes, sizes[1:]):
            self.assertLessEqual(previous, current, f"棋盘尺寸曲线：{sizes}")


class TestParseArt(unittest.TestCase):
    """字符画解析。"""

    def test_解析四个方向(self) -> None:
        rows, cols, arrows = parse_art("^ v < >")
        self.assertEqual((rows, cols), (1, 4))
        self.assertEqual(
            [a.direction for a in arrows],
            [Direction.UP, Direction.DOWN, Direction.LEFT, Direction.RIGHT],
        )

    def test_忽略缩进与空行(self) -> None:
        rows, cols, arrows = parse_art("""
            > . ^

            . v .
        """)
        self.assertEqual((rows, cols), (2, 3))
        self.assertEqual(len(arrows), 3)
        self.assertEqual(arrows[0].cell, (0, 0))

    def test_各行宽度不一致时报错(self) -> None:
        with self.assertRaises(ValueError):
            parse_art("> . .\n. .")

    def test_无法识别的符号报错(self) -> None:
        with self.assertRaises(ValueError):
            parse_art("> . X")


if __name__ == "__main__":
    unittest.main(verbosity=2)
