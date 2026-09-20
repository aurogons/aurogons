"""棋盘逻辑的单元测试，对应作业要求的 T01 ~ T06。

这些测试只依赖 game.board —— 该模块不导入 pygame，所以整套测试
不需要显示器，跑起来很快：

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import unittest

from game.board import Arrow, Board, ClickResult, Direction, GameState
from game.levels import parse_art


def make_board(art: str, max_misses: int = 3) -> Board:
    """由字符画构造棋盘，方便用例里直观看清布局。"""
    rows, cols, arrows = parse_art(art)
    return Board(rows, cols, arrows, max_misses)


class TestPathDetection(unittest.TestCase):
    """路径检测本身的行为（作业「箭头与路径判断」一项）。"""

    def test_作业示例一_右侧有箭头阻挡不能飞出(self) -> None:
        """作业原文例子： -> . . ^ .  """
        board = make_board("> . . ^ .")
        first = board.arrows[(0, 0)]
        self.assertFalse(board.is_free(first))
        self.assertEqual(board.blocker_of(first).cell, (0, 3))

    def test_作业示例二_右侧无阻挡可以飞出(self) -> None:
        """作业原文例子： ^ . . . ->  """
        board = make_board("^ . . . >")
        last = board.arrows[(0, 4)]
        self.assertTrue(board.is_free(last))

    def test_路径只包含棋盘内的格子(self) -> None:
        """path() 不会产出越界坐标 —— 这是不越界的关键保证。"""
        board = make_board("""
            v . .
            . . .
            . . ^
        """)
        self.assertEqual(list(board.path(board.arrows[(0, 0)])), [(1, 0), (2, 0)])
        self.assertEqual(
            list(board.path(board.arrows[(2, 2)])), [(1, 2), (0, 2)]
        )

    def test_四个方向各只走自己那条线(self) -> None:
        """四个箭头都朝内指，各自沿所在的行或列走到棋盘外。"""
        board = make_board("""
            . v .
            > . <
            . ^ .
        """)
        expected = {
            (0, 1): [(1, 1), (2, 1)],   # 下
            (1, 0): [(1, 1), (1, 2)],   # 右
            (1, 2): [(1, 1), (1, 0)],   # 左
            (2, 1): [(1, 1), (0, 1)],   # 上
        }
        for cell, path in expected.items():
            with self.subTest(cell=cell):
                self.assertEqual(list(board.path(board.arrows[cell])), path)

    def test_阻挡取的是前方第一个箭头(self) -> None:
        """同一条线上有多个箭头时，只有最近的那个算挡路的。"""
        board = make_board("> . ^ . ^")
        blocker = board.blocker_of(board.arrows[(0, 0)])
        self.assertEqual(blocker.cell, (0, 2))

    def test_相邻箭头互相阻挡(self) -> None:
        board = make_board("> < .")
        self.assertFalse(board.is_free(board.arrows[(0, 0)]))
        self.assertFalse(board.is_free(board.arrows[(0, 1)]))


class TestT01FreeArrowFliesOut(unittest.TestCase):
    """T01 点击前方无阻挡的箭头 → 箭头飞出棋盘并消失。"""

    def test_无阻挡时飞出并消失(self) -> None:
        board = make_board("> . . .", max_misses=3)
        self.assertTrue(board.is_free(board.arrows[(0, 0)]))

        result = board.click(0, 0)

        self.assertIs(result, ClickResult.FLY_OUT)
        self.assertNotIn((0, 0), board.arrows)
        self.assertEqual(board.remaining, 0)

    def test_飞出不影响失误次数(self) -> None:
        board = make_board("> . . .", max_misses=3)
        board.click(0, 0)
        self.assertEqual(board.misses_left, 3)

    def test_清空后判定为通关(self) -> None:
        board = make_board("> . .", max_misses=3)
        board.click(0, 0)
        self.assertIs(board.state, GameState.WIN)


class TestT02BlockedArrow(unittest.TestCase):
    """T02 点击前方有阻挡的箭头 → 箭头不消失，失误次数减 1。"""

    def test_有阻挡时不消失且扣失误(self) -> None:
        board = make_board("> . ^ .", max_misses=3)

        result = board.click(0, 0)

        self.assertIs(result, ClickResult.BLOCKED)
        self.assertIn((0, 0), board.arrows)      # 箭头还在
        self.assertEqual(board.remaining, 2)
        self.assertEqual(board.misses_left, 2)   # 3 -> 2

    def test_阻挡时状态仍是进行中(self) -> None:
        board = make_board("> . ^ .", max_misses=3)
        board.click(0, 0)
        self.assertIs(board.state, GameState.PLAYING)

    def test_移走挡路箭头后即可飞出(self) -> None:
        board = make_board("> . ^ .", max_misses=3)
        board.click(0, 0)                 # 被挡住，扣一次
        board.click(0, 2)                 # 放走挡路的箭头（它朝上，能飞出去）

        self.assertIs(board.click(0, 0), ClickResult.FLY_OUT)
        self.assertEqual(board.misses_left, 2)


class TestT03EdgeArrows(unittest.TestCase):
    """T03 点击位于边缘且朝向棋盘外的箭头 → 正常消失，不发生越界错误。"""

    def test_四条边朝外的箭头都能飞出(self) -> None:
        art = """
            . ^ .
            < . >
            . v .
        """
        for cell in [(0, 1), (1, 0), (1, 2), (2, 1)]:
            with self.subTest(cell=cell):
                board = make_board(art, max_misses=3)
                self.assertTrue(board.is_free(board.arrows[cell]))
                self.assertIs(board.click(*cell), ClickResult.FLY_OUT)

    def test_单行单列边界不越界(self) -> None:
        """棋盘退化成一行 / 一列时也不能抛 IndexError。"""
        for art in ("> . .", "^\n.\n."):
            with self.subTest(art=art):
                board = make_board(art, max_misses=3)
                origin = (0, 0)
                self.assertIs(board.click(*origin), ClickResult.FLY_OUT)

    def test_朝外的箭头路径为空(self) -> None:
        board = make_board("""
            ^ . .
            . . .
            . . v
        """)
        self.assertEqual(list(board.path(board.arrows[(0, 0)])), [])
        self.assertEqual(list(board.path(board.arrows[(2, 2)])), [])


class TestT04ClearAllArrows(unittest.TestCase):
    """T04 消除本关全部箭头 → 显示通关。"""

    def test_按顺序清空后通关(self) -> None:
        board = make_board("""
            > . ^
            . . .
        """, max_misses=3)

        self.assertIs(board.click(0, 2), ClickResult.FLY_OUT)   # 先放走挡路的
        self.assertIs(board.state, GameState.PLAYING)

        self.assertIs(board.click(0, 0), ClickResult.FLY_OUT)
        self.assertIs(board.state, GameState.WIN)
        self.assertEqual(board.remaining, 0)

    def test_通关后剩余失误不影响判定(self) -> None:
        board = make_board("^ .", max_misses=1)
        board.click(0, 0)
        self.assertIs(board.state, GameState.WIN)


class TestT05MissesExhausted(unittest.TestCase):
    """T05 失误次数耗尽 → 显示失败并允许重新开始。"""

    def test_失误扣到零判定失败(self) -> None:
        board = make_board("> . ^ .", max_misses=2)

        self.assertIs(board.click(0, 0), ClickResult.BLOCKED)
        self.assertIs(board.state, GameState.PLAYING)
        self.assertEqual(board.misses_left, 1)

        self.assertIs(board.click(0, 0), ClickResult.BLOCKED)
        self.assertIs(board.state, GameState.LOSE)
        self.assertEqual(board.misses_left, 0)

    def test_失误为零后继续点不再扣成负数(self) -> None:
        board = make_board("> . ^ .", max_misses=1)
        board.click(0, 0)
        self.assertIs(board.state, GameState.LOSE)

        board.click(0, 0)
        board.click(0, 0)
        self.assertEqual(board.misses_left, 0)

    def test_失败后点击不再改变棋盘(self) -> None:
        board = make_board("> . ^ .", max_misses=1)
        board.click(0, 0)                       # 失败

        self.assertIs(board.click(0, 2), ClickResult.IGNORED)
        self.assertIn((0, 2), board.arrows)

    def test_失败后可以重新开始(self) -> None:
        board = make_board("> . ^ .", max_misses=1)
        board.click(0, 0)
        board.reset()

        self.assertIs(board.state, GameState.PLAYING)
        self.assertEqual(board.misses_left, 1)
        self.assertEqual(board.remaining, 2)


class TestT06Restart(unittest.TestCase):
    """T06 游戏进行中重新开始 → 箭头布局和失误次数恢复。"""

    def test_重新开始恢复布局与失误(self) -> None:
        board = make_board("> . ^ .", max_misses=3)
        board.click(0, 2)                 # 放走一个箭头
        board.click(0, 0)                 # 再点错一次
        self.assertNotEqual(board.remaining, board.total_arrows)

        board.reset()

        self.assertEqual(board.remaining, board.total_arrows)
        self.assertEqual(board.misses_left, board.max_misses)
        self.assertEqual(board.cleared, 0)
        self.assertIs(board.state, GameState.PLAYING)
        self.assertEqual(board.render_ascii(), "> . ^ .")

    def test_重新开始后仍可正常通关(self) -> None:
        board = make_board("> . ^", max_misses=3)
        board.click(0, 0)
        board.reset()

        board.click(0, 2)
        board.click(0, 0)
        self.assertIs(board.state, GameState.WIN)


class TestEdgeCases(unittest.TestCase):
    """补充的边界情况。"""

    def test_点击空格不计失误(self) -> None:
        board = make_board("> . . ^", max_misses=3)
        self.assertIs(board.click(0, 1), ClickResult.IGNORED)
        self.assertEqual(board.misses_left, 3)

    def test_点击越界坐标不计失误也不报错(self) -> None:
        board = make_board("> . . ^", max_misses=3)
        for cell in [(-1, 0), (0, -1), (9, 9), (0, 4)]:
            with self.subTest(cell=cell):
                self.assertIs(board.click(*cell), ClickResult.IGNORED)
        self.assertEqual(board.misses_left, 3)

    def test_点击已经飞出的位置不计失误(self) -> None:
        # 棋盘上留一个别的箭头，避免清空后进入通关状态干扰本用例
        board = make_board("""
            > . . .
            . . . ^
        """, max_misses=3)
        self.assertIs(board.click(0, 0), ClickResult.FLY_OUT)

        self.assertIs(board.click(0, 0), ClickResult.IGNORED)
        self.assertEqual(board.misses_left, 3)

    def test_单箭头棋盘(self) -> None:
        board = make_board(">", max_misses=1)
        self.assertEqual(board.remaining, 1)
        self.assertIs(board.click(0, 0), ClickResult.FLY_OUT)
        self.assertIs(board.state, GameState.WIN)

    def test_空棋盘直接算通关(self) -> None:
        """「清空全部箭头即通关」，空棋盘自然满足，状态定义要自洽。"""
        board = Board(2, 2, [], max_misses=3)
        self.assertEqual(board.remaining, 0)
        self.assertEqual(board.free_arrows(), [])
        self.assertIs(board.state, GameState.WIN)

    def test_关卡解析拒绝空布局(self) -> None:
        with self.assertRaises(ValueError):
            parse_art(". . .")

    def test_非法参数被拒绝(self) -> None:
        with self.assertRaises(ValueError):
            Board(0, 3, [], max_misses=1)           # 尺寸非正
        with self.assertRaises(ValueError):
            Board(3, 3, [], max_misses=0)           # 失误上限非正
        with self.assertRaises(ValueError):
            Board(2, 2, [Arrow(5, 0, Direction.UP)], max_misses=1)   # 越界箭头
        with self.assertRaises(ValueError):
            Board(2, 2, [Arrow(0, 0, Direction.UP), Arrow(0, 0, Direction.DOWN)],
                  max_misses=1)                     # 同格重复


class TestSnapshotRestore(unittest.TestCase):
    """撤销功能依赖的快照 / 还原必须是完整还原。"""

    def test_快照还原恢复全部状态(self) -> None:
        board = make_board("> . ^ .", max_misses=3)
        before = board.snapshot()

        board.click(0, 2)
        board.click(0, 0)

        board.restore(before)

        self.assertEqual(board.remaining, 2)
        self.assertEqual(board.misses_left, 3)
        self.assertEqual(board.cleared, 0)
        self.assertIs(board.state, GameState.PLAYING)
        self.assertEqual(board.render_ascii(), "> . ^ .")

    def test_还原失败状态(self) -> None:
        board = make_board("> . ^ .", max_misses=1)
        alive = board.snapshot()
        board.click(0, 0)
        self.assertIs(board.state, GameState.LOSE)

        board.restore(alive)
        self.assertIs(board.state, GameState.PLAYING)


class TestFreeArrows(unittest.TestCase):
    """提示功能依赖 free_arrows()。"""

    def test_列出全部可飞出的箭头(self) -> None:
        board = make_board("""
            > . ^
            . v .
        """)
        free = {(a.row, a.col) for a in board.free_arrows()}
        # (0,2)^ 朝上、 (1,1)v 朝下，两者前方都畅通
        self.assertEqual(free, {(0, 2), (1, 1)})

    def test_飞出的箭头不再是可选项(self) -> None:
        board = make_board("> . .", max_misses=1)
        board.click(0, 0)
        self.assertEqual(board.free_arrows(), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
