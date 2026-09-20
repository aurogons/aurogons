"""关卡数据。

关卡用**字符画**描述：``.`` 是空格，``^ v < >`` 是四个方向的箭头，
同行各列之间用空格分隔。这样布局在源码里一眼就能看懂 ——
助教问「这一关为什么这样摆」时，可以直接指着代码回答，
而不是对着一串坐标元组干瞪眼。

设计关卡时有一条硬约束：**同一条直线上的两个箭头不能正面相对**。
例如同一行里 ``> . <``，右边的箭头挡住左边，左边的也挡住右边，
两者谁也飞不出去，这一关就死锁了。想造「链式阻挡」应该让同一条线上
的箭头朝向一致（都朝上或都朝下），这样最上面的飞走后，下面的依次解锁。

每加一关都应跑 ``python tools/validate_levels.py`` 验证可通关。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from .board import Arrow, Board, Direction

#: 字符画符号到方向的映射
_CHAR_TO_DIRECTION = {
    "^": Direction.UP,
    "v": Direction.DOWN,
    "<": Direction.LEFT,
    ">": Direction.RIGHT,
}


@dataclass(frozen=True)
class Level:
    """一个关卡的定义。"""

    name: str
    art: str
    max_misses: int
    note: str = ""


LEVELS: List[Level] = [
    Level(
        name="第一关 · 初识规则",
        art="""
            . . . .
            > . . ^
            . . . .
            . v < .
        """,
        max_misses=5,
        note="教学关。两个箭头一开始就能飞出，另外两个被挡住，先清掉挡路的即可。",
    ),
    Level(
        name="第二关 · 阻挡链",
        art="""
            . v . .
            > . . ^
            . . . ^
            . < . v
        """,
        max_misses=5,
        note="右侧出现一列两个同向箭头，必须自上而下依次解锁。",
    ),
    Level(
        name="第三关 · 拆外圈",
        art="""
            v . v . .
            > . . ^ .
            . . . ^ .
            . . . ^ <
            > v . . .
        """,
        max_misses=4,
        note="中间一列三个同向箭头是突破口，先把它拆掉才能放出左右两侧的箭头。",
    ),
    Level(
        name="第四关 · 长距离阻挡",
        art="""
            v . v . .
            > v . . ^
            > . > . .
            . . . v <
            > . v . ^
        """,
        max_misses=4,
        note="多处出现跨越多格的远距离阻挡，需要顺着整行整列看，不能只看相邻格。",
    ),
    Level(
        name="第五关 · 综合",
        art="""
            v . v . v .
            > v . . . ^
            > . > . . ^
            . . . v . .
            > . v . > .
            v . v . . ^
        """,
        max_misses=3,
        note="6x6 大棋盘，纵列上有三层同向箭头，容错只有 3 次。",
    ),
]


def parse_art(art: str) -> Tuple[int, int, List[Arrow]]:
    """把字符画解析成 ``(rows, cols, arrows)``。

    每行行首行尾的空格会被忽略；各行必须等宽，否则说明画的时候手滑了，
    直接报错比默默画出一个错位的棋盘要好。
    """
    lines = [ln for ln in (raw.strip() for raw in art.strip().splitlines()) if ln]
    if not lines:
        raise ValueError("关卡字符画是空的")

    grid = [ln.split() for ln in lines]
    widths = {len(row) for row in grid}
    if len(widths) != 1:
        raise ValueError(f"关卡字符画各行宽度不一致：{[len(r) for r in grid]}")

    rows = len(grid)
    cols = widths.pop()

    arrows: List[Arrow] = []
    for row_index, row in enumerate(grid):
        for col_index, token in enumerate(row):
            if token == ".":
                continue
            try:
                direction = _CHAR_TO_DIRECTION[token]
            except KeyError:
                raise ValueError(
                    f"第 {row_index + 1} 行第 {col_index + 1} 列出现无法识别的符号 "
                    f"{token!r}，只允许 . ^ v < >"
                ) from None
            arrows.append(Arrow(row_index, col_index, direction))

    if not arrows:
        raise ValueError("关卡里一个箭头都没有")

    return rows, cols, arrows


def build_board(level: Level) -> Board:
    """由关卡定义构造一个全新的棋盘。"""
    rows, cols, arrows = parse_art(level.art)
    return Board(rows, cols, arrows, level.max_misses)
