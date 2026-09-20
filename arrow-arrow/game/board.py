"""棋盘、箭头与路径检测 —— 游戏的纯逻辑核心。

这个模块刻意 **不导入 pygame**：规则判定与图形渲染完全分离，因此全部核心逻辑
都能在没有显示器的环境下直接跑单元测试（见 tests/test_board.py）。

坐标约定：row 向下递增，col 向右递增，(0, 0) 位于棋盘左上角。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterator, List, Optional, Tuple


class Direction(Enum):
    """箭头方向。

    枚举值是前进增量 ``(drow, dcol)``，路径检测直接取用，
    这样四个方向可以共用同一段推进逻辑，不必写四套分支。
    """

    UP = (-1, 0)
    DOWN = (1, 0)
    LEFT = (0, -1)
    RIGHT = (0, 1)

    @property
    def delta(self) -> Tuple[int, int]:
        """返回 ``(drow, dcol)``。"""
        return self.value

    @property
    def char(self) -> str:
        """返回该方向在关卡字符画中的符号。"""
        return _DIRECTION_TO_CHAR[self]


_DIRECTION_TO_CHAR = {
    Direction.UP: "^",
    Direction.DOWN: "v",
    Direction.LEFT: "<",
    Direction.RIGHT: ">",
}
_CHAR_TO_DIRECTION = {c: d for d, c in _DIRECTION_TO_CHAR.items()}


@dataclass(frozen=True)
class Arrow:
    """棋盘上的一个箭头。不可变，便于安全地放进集合与快照。"""

    row: int
    col: int
    direction: Direction

    @property
    def cell(self) -> Tuple[int, int]:
        return (self.row, self.col)


class ClickResult(Enum):
    """一次点击的结果。"""

    FLY_OUT = "fly_out"   # 前方无阻挡：箭头飞出棋盘并消失
    BLOCKED = "blocked"   # 前方有阻挡：箭头不动，扣一次失误
    IGNORED = "ignored"   # 点空、越界或本关已结束：不计失误


class GameState(Enum):
    """本关的整体状态。"""

    PLAYING = "playing"
    WIN = "win"
    LOSE = "lose"


@dataclass(frozen=True)
class BoardSnapshot:
    """棋盘在某一时刻的完整状态，用于「撤销上一步」。"""

    arrows: Dict[Tuple[int, int], Arrow]
    misses_left: int
    cleared: int
    state: GameState


class Board:
    """一个关卡的棋盘。

    箭头存放在 ``dict[(row, col)] -> Arrow`` 里，而不是二维数组：
    棋盘通常是稀疏的，字典既省空间，又天然没有「格子里有没有箭头」的
    空值判断，越界坐标也只会取到 ``None`` 而不会抛 IndexError。
    """

    def __init__(
        self,
        rows: int,
        cols: int,
        arrows: List[Arrow],
        max_misses: int,
    ) -> None:
        if rows <= 0 or cols <= 0:
            raise ValueError(f"棋盘尺寸必须为正数，收到 {rows}x{cols}")
        if max_misses <= 0:
            raise ValueError(f"失误次数必须为正数，收到 {max_misses}")

        seen = set()
        for a in arrows:
            if not (0 <= a.row < rows and 0 <= a.col < cols):
                raise ValueError(f"箭头 {a} 超出 {rows}x{cols} 棋盘范围")
            if a.cell in seen:
                raise ValueError(f"格 {a.cell} 上有重复的箭头")
            seen.add(a.cell)

        self.rows = rows
        self.cols = cols
        self.max_misses = max_misses
        self._initial: Tuple[Arrow, ...] = tuple(arrows)
        self.reset()

    # ------------------------------------------------------------------
    # 状态
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """恢复到关卡初始状态（对应测试 T06）。"""
        self.arrows: Dict[Tuple[int, int], Arrow] = {
            a.cell: a for a in self._initial
        }
        self.misses_left = self.max_misses
        self.cleared = 0
        # 「清空全部箭头即通关」，所以本来就空的棋盘一开始就是通关状态。
        # 正常关卡不会为空（parse_art 会拦下来），这里只是让状态定义自洽。
        self.state = GameState.WIN if not self.arrows else GameState.PLAYING

    @property
    def total_arrows(self) -> int:
        """本关箭头总数。"""
        return len(self._initial)

    @property
    def remaining(self) -> int:
        """剩余箭头数量。"""
        return len(self.arrows)

    @property
    def is_over(self) -> bool:
        return self.state is not GameState.PLAYING

    # ------------------------------------------------------------------
    # 路径检测（本项目的核心算法）
    # ------------------------------------------------------------------

    def path(self, arrow: Arrow) -> Iterator[Tuple[int, int]]:
        """按箭头朝向，依次产出它前方棋盘内的所有格子。

        只产出**棋盘内**的格子；一旦走出去就停下 —— 因此调用方拿到的
        坐标永远合法，不需要自己再做边界判断。
        """
        drow, dcol = arrow.direction.delta
        row = arrow.row + drow
        col = arrow.col + dcol
        while 0 <= row < self.rows and 0 <= col < self.cols:
            yield (row, col)
            row += drow
            col += dcol

    def is_free(self, arrow: Arrow) -> bool:
        """箭头前方到棋盘边界之间是否没有其他箭头阻挡。"""
        return all(cell not in self.arrows for cell in self.path(arrow))

    def blocker_of(self, arrow: Arrow) -> Optional[Arrow]:
        """返回挡在箭头前方的第一个箭头；前方畅通则返回 None。

        界面用它来高亮「是谁挡住了我」，让碰撞反馈更有信息量。
        """
        for cell in self.path(arrow):
            blocker = self.arrows.get(cell)
            if blocker is not None:
                return blocker
        return None

    def free_arrows(self) -> List[Arrow]:
        """当前所有可以飞出的箭头，供「提示」功能使用。"""
        return [a for a in self.arrows.values() if self.is_free(a)]

    # ------------------------------------------------------------------
    # 交互
    # ------------------------------------------------------------------

    def click(self, row: int, col: int) -> ClickResult:
        """点击 ``(row, col)`` 格，返回本次点击的结果。

        点空、越界或本关已结束时返回 ``IGNORED``，**不扣失误**；
        这样玩家在结算画面上乱点不会误伤统计。
        """
        if self.state is not GameState.PLAYING:
            return ClickResult.IGNORED

        arrow = self.arrows.get((row, col))
        if arrow is None:
            return ClickResult.IGNORED

        if self.is_free(arrow):
            del self.arrows[arrow.cell]
            self.cleared += 1
            if not self.arrows:
                self.state = GameState.WIN
            return ClickResult.FLY_OUT

        self.misses_left -= 1
        if self.misses_left <= 0:
            self.misses_left = 0
            self.state = GameState.LOSE
        return ClickResult.BLOCKED

    # ------------------------------------------------------------------
    # 撤销
    # ------------------------------------------------------------------

    def snapshot(self) -> BoardSnapshot:
        return BoardSnapshot(
            arrows=dict(self.arrows),
            misses_left=self.misses_left,
            cleared=self.cleared,
            state=self.state,
        )

    def restore(self, snap: BoardSnapshot) -> None:
        self.arrows = dict(snap.arrows)
        self.misses_left = snap.misses_left
        self.cleared = snap.cleared
        self.state = snap.state

    # ------------------------------------------------------------------
    # 调试辅助
    # ------------------------------------------------------------------

    def render_ascii(self) -> str:
        """把棋盘画成字符画，方便调试和关卡设计时肉眼检查。"""
        lines = []
        for row in range(self.rows):
            cells = []
            for col in range(self.cols):
                arrow = self.arrows.get((row, col))
                cells.append(arrow.direction.char if arrow else ".")
            lines.append(" ".join(cells))
        return "\n".join(lines)
