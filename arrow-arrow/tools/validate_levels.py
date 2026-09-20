"""关卡校验器：检查全部关卡是否真的能通关。

为什么这件事可以自动做
----------------------
游戏规则下，消除一个箭头只会让棋盘更空，**不可能**把别的箭头从
「可飞出」变回「被阻挡」。也就是说「当前可飞出的箭头集合」随着消除
单调递增 —— 已经解锁的箭头永远是解锁的。

于是：
  * 如果这一关存在通关顺序，那么「反复消除任意一个当前可飞出的箭头」
    这种贪心策略一定也能清空棋盘（先走哪一步都不会把路走死）；
  * 反过来，如果贪心过程中卡住了（还剩箭头，但没有任何一个能飞出），
    这一关就**必定无解**，不存在某条巧妙路线能救回来。

所以关卡不需要靠人肉穷举试玩来验证。改完关卡数据请重跑本脚本。

用法：
    python tools/validate_levels.py
    python tools/validate_levels.py --show-solution    # 顺便打印贪心解法顺序
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Windows 控制台默认用 GBK 编码，中文会变成乱码；这里强制走 UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from game.board import Arrow, Board  # noqa: E402
from game.levels import LEVELS, Level, build_board  # noqa: E402


class SolveResult:
    """一关的求解结果。"""

    def __init__(
        self,
        solved: bool,
        order: List[Arrow],
        stuck: List[Arrow],
        initial_free: int,
    ) -> None:
        self.solved = solved
        self.order = order
        self.stuck = stuck
        self.initial_free = initial_free


def find_mutual_blocks(board: Board) -> List[Tuple[Arrow, Arrow]]:
    """找出互相阻挡的箭头对 —— 关卡设计里最致命的一种错误。

    如果 A 前方的第一个箭头是 B，而 B 前方的第一个箭头又是 A，那么
    要放走 A 必须先移走 B，要移走 B 又必须先放走 A，构成死循环。
    这类布局**无论怎么玩都无解**，而且用肉眼看字符画时很容易漏掉
    （尤其当两个箭头隔了好几格，中间还夹着别的空格时）。

    这里把它单独检出来，是为了让报错直接指向病根，而不只是说「卡住了」。
    """
    pairs: List[Tuple[Arrow, Arrow]] = []
    for arrow in board.arrows.values():
        blocker = board.blocker_of(arrow)
        if blocker is not None and board.blocker_of(blocker) is arrow:
            # 每对会被数到两次，去重时只保留 row/col 顺序靠前的那次
            if arrow.cell < blocker.cell:
                pairs.append((arrow, blocker))
    return pairs


def solve(board: Board) -> SolveResult:
    """贪心求解。返回是否通关、消除顺序、以及卡住时剩余的箭头。"""
    initial_free = len(board.free_arrows())
    order: List[Arrow] = []

    while board.remaining > 0:
        free = board.free_arrows()
        if not free:
            # 还剩箭头却一个都飞不出去 —— 死局
            return SolveResult(False, order, list(board.arrows.values()), initial_free)

        target = free[0]
        board.click(target.row, target.col)
        order.append(target)

    return SolveResult(True, order, [], initial_free)


def _describe(arrow: Arrow) -> str:
    return f"({arrow.row},{arrow.col}){arrow.direction.char}"


def check_level(level: Level, index: int, show_solution: bool) -> bool:
    """校验单个关卡，打印报告并返回是否通过。"""
    board = build_board(level)
    total = board.total_arrows
    initial_free = len(board.free_arrows())
    free_ratio = initial_free / total if total else 0.0

    print(f"[{index}] {level.name}")
    print(f"    棋盘 {board.rows}x{board.cols}｜箭头 {total} 个｜失误上限 {board.max_misses}")
    print(f"    初始可飞出 {initial_free} 个（占 {free_ratio:.0%}，越低越难）")

    # 先查初始布局里有没有互相阻挡的箭头对 —— 有的话这关一定无解
    initial_pairs = find_mutual_blocks(board)

    result = solve(board)

    if result.solved:
        print(f"    \033[32m可通关\033[0m：贪心解法 {len(result.order)} 步清空棋盘")
        if show_solution:
            steps = " -> ".join(_describe(a) for a in result.order)
            print(f"    解法顺序：{steps}")
        print()
        return True

    print(f"    \033[31m无法通关\033[0m：卡住时还剩 {len(result.stuck)} 个箭头")

    if initial_pairs:
        print("    病根（初始布局就互相阻挡，必定无解）：")
        for a, b in initial_pairs:
            print(f"        {_describe(a)} 与 {_describe(b)} 正面相对，谁也飞不出去")
    else:
        # 初始没问题，说明死锁是玩到中途才形成的，去卡住的局面里找
        stuck_pairs = find_mutual_blocks(board)
        if stuck_pairs:
            print("    病根（消除若干箭头后形成互相阻挡）：")
            for a, b in stuck_pairs:
                print(f"        {_describe(a)} 与 {_describe(b)} 正面相对，谁也飞不出去")
        print("    卡住的箭头：" + "、".join(_describe(a) for a in result.stuck))

    print()
    return False


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="校验全部关卡是否可通关")
    parser.add_argument(
        "--show-solution",
        action="store_true",
        help="打印每关的贪心解法顺序",
    )
    args = parser.parse_args(argv)

    print("=" * 56)
    print("关卡校验")
    print("=" * 56)

    results = [
        check_level(level, i, args.show_solution)
        for i, level in enumerate(LEVELS, start=1)
    ]

    passed = sum(results)
    total = len(results)
    print("=" * 56)
    if passed == total:
        print(f"\033[32m全部 {total} 关均可通关。\033[0m")
        return 0

    print(f"\033[31m{total - passed}/{total} 关无法通关，请调整关卡数据。\033[0m")
    return 1


if __name__ == "__main__":
    sys.exit(main())
