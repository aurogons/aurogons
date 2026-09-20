"""开始 / 游戏 / 结果三个场景，以及管理它们的 App。"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import pygame

from . import config, ui
from .anim import FlyOutAnimation, HighlightAnimation, ShakeAnimation, Toast
from .board import Board, BoardSnapshot, ClickResult, GameState
from .levels import LEVELS, Level, build_board

Cell = Tuple[int, int]


def format_time(seconds: float) -> str:
    """把秒数格式化成 ``MM:SS``。"""
    total = int(seconds)
    return f"{total // 60:02d}:{total % 60:02d}"


# ======================================================================
# 场景基类
# ======================================================================


class Scene:
    """场景基类。子类按需覆写三个钩子。"""

    def handle_event(self, event: pygame.event.Event) -> None:
        """处理一个输入事件。"""

    def update(self, dt: float) -> None:
        """按经过的秒数推进动画与计时。"""

    def draw(self, surface: pygame.Surface) -> None:
        """把自己画到 ``surface`` 上。"""


# ======================================================================
# 开始界面
# ======================================================================


class StartScene(Scene):
    """标题、开始游戏、关卡选择、退出。"""

    def __init__(self, app: "App") -> None:
        self.app = app
        self.buttons: List[ui.Button] = []

        center_x = config.WINDOW_WIDTH // 2

        self.buttons.append(
            ui.Button(
                (center_x - 130, 236, 260, 60),
                "开 始 游 戏",
                self.app.start_new_game,
                font_size=config.FONT_SIZE_HEADING,
            )
        )

        # 关卡选择：一行按钮，未解锁的置灰不可点
        count = len(LEVELS)
        size, gap = 92, 16
        total = count * size + (count - 1) * gap
        left = center_x - total // 2
        for index in range(count):
            unlocked = index < self.app.unlocked
            self.buttons.append(
                ui.Button(
                    (left + index * (size + gap), 378, size, 58),
                    str(index + 1),
                    self._make_level_jump(index),
                    enabled=unlocked,
                )
            )

        self.buttons.append(
            ui.Button(
                (center_x - 90, 470, 180, 50),
                "退 出",
                self.app.quit,
                font_size=config.FONT_SIZE_SMALL,
            )
        )

    def _make_level_jump(self, index: int):
        def jump() -> None:
            self.app.start_level(index)

        return jump

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self.app.start_new_game()
            return
        for button in self.buttons:
            button.handle_event(event)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(config.COLOR_BG)

        center_x = config.WINDOW_WIDTH // 2
        ui.draw_text(
            surface,
            "一 箭 又 一 箭",
            (center_x, 108),
            config.FONT_SIZE_TITLE,
            config.COLOR_TEXT,
            anchor="center",
            bold=True,
        )
        ui.draw_text(
            surface,
            "看准方向，按顺序点击箭头，让它们依次飞出棋盘",
            (center_x, 172),
            config.FONT_SIZE_NORMAL,
            config.COLOR_TEXT_DIM,
            anchor="center",
        )

        ui.draw_text(
            surface,
            "关卡选择",
            (center_x, 344),
            config.FONT_SIZE_SMALL,
            config.COLOR_TEXT_DIM,
            anchor="center",
        )
        ui.draw_text(
            surface,
            "（灰色关卡尚未解锁）",
            (center_x, 452),
            config.FONT_SIZE_SMALL,
            config.COLOR_TEXT_DIM,
            anchor="center",
        )

        for button in self.buttons:
            button.draw(surface)

        tips = [
            "操作说明：鼠标左键点击箭头",
            "前方没有其他箭头 → 箭头飞出棋盘并消失",
            "前方有箭头阻挡 → 箭头飞不出去，剩余失误次数 -1",
            "失误次数用尽则本关失败；清空全部箭头即可进入下一关",
        ]
        for i, line in enumerate(tips):
            ui.draw_text(
                surface,
                line,
                (center_x, 560 + i * 30),
                config.FONT_SIZE_SMALL,
                config.COLOR_TEXT_DIM,
                anchor="center",
            )


# ======================================================================
# 游戏界面
# ======================================================================


class PlayScene(Scene):
    """棋盘、信息栏、动画与交互。"""

    def __init__(self, app: "App", level_index: int) -> None:
        self.app = app
        self.level_index = level_index
        self.level: Level = LEVELS[level_index]
        self.board: Board = build_board(self.level)

        self.play_time = 0.0
        self.history: List[BoardSnapshot] = []
        self.hint_rotation = 0

        # 动画与临时提示；它们只影响画面，不影响规则
        self.flying: List[FlyOutAnimation] = []
        self.shaking: Dict[Cell, ShakeAnimation] = {}
        self.highlights: List[HighlightAnimation] = []
        self.toast: Optional[Toast] = None
        self.exit_timer: Optional[float] = None

        self._compute_geometry()
        self._build_buttons()
        # 正常关卡进来都是进行中；这里只是兜住「初始即通关」的退化情形
        self._on_board_changed()

    # ------------------------------------------------------------ 布局

    def _compute_geometry(self) -> None:
        """按棋盘大小算出格子边长与棋盘左上角，使其在可用区域内居中。"""
        area_left = config.BOARD_AREA_SIDE_MARGIN
        area_top = config.BOARD_AREA_TOP
        avail_w = config.WINDOW_WIDTH - 2 * config.BOARD_AREA_SIDE_MARGIN
        avail_h = (
            config.WINDOW_HEIGHT - config.BOARD_AREA_BOTTOM_MARGIN - config.BOARD_AREA_TOP
        )

        cell = min(
            config.MAX_CELL_SIZE,
            avail_w // self.board.cols,
            avail_h // self.board.rows,
        )
        self.cell_size = max(config.MIN_CELL_SIZE, cell)

        board_w = self.cell_size * self.board.cols
        board_h = self.cell_size * self.board.rows
        self.board_origin = (
            area_left + (avail_w - board_w) // 2,
            area_top + (avail_h - board_h) // 2,
        )

    def cell_center(self, row: int, col: int) -> Tuple[float, float]:
        """格子中心在屏幕上的坐标。"""
        ox, oy = self.board_origin
        return (
            ox + col * self.cell_size + self.cell_size / 2,
            oy + row * self.cell_size + self.cell_size / 2,
        )

    def cell_rect(self, row: int, col: int) -> pygame.Rect:
        ox, oy = self.board_origin
        return pygame.Rect(
            ox + col * self.cell_size,
            oy + row * self.cell_size,
            self.cell_size,
            self.cell_size,
        )

    def cell_at(self, pos: Tuple[int, int]) -> Optional[Cell]:
        """屏幕坐标 -> 棋盘格；点在棋盘外返回 None。"""
        ox, oy = self.board_origin
        col = (pos[0] - ox) // self.cell_size
        row = (pos[1] - oy) // self.cell_size
        if 0 <= row < self.board.rows and 0 <= col < self.board.cols:
            return (int(row), int(col))
        return None

    def _build_buttons(self) -> None:
        right = config.WINDOW_WIDTH - config.BOARD_AREA_SIDE_MARGIN
        y, height = 20, 38
        specs = [
            ("提示", 76, self.use_hint),
            ("撤销", 76, self.undo),
            ("重新开始", 104, self.restart),
            ("返回", 76, self.app.go_start),
        ]
        self.buttons: List[ui.Button] = []
        x = right
        for text, width, callback in reversed(specs):
            x -= width
            self.buttons.append(
                ui.Button((x, y, width, height), text, callback, font_size=config.FONT_SIZE_SMALL)
            )
            x -= 10
        self.buttons.reverse()

    # ------------------------------------------------------------ 输入

    def handle_event(self, event: pygame.event.Event) -> None:
        for button in self.buttons:
            button.handle_event(event)

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_r:
                self.restart()
            elif event.key == pygame.K_h:
                self.use_hint()
            elif event.key == pygame.K_z:
                self.undo()
            elif event.key == pygame.K_ESCAPE:
                self.app.go_start()
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            cell = self.cell_at(event.pos)
            if cell is not None:
                self._click_cell(*cell)

    # ------------------------------------------------------------ 交互

    def _click_cell(self, row: int, col: int) -> None:
        arrow = self.board.arrows.get((row, col))
        if arrow is None:
            return

        # 快照要在点击之前拍，撤销时才能回到「这一下还没点」的状态
        snapshot = self.board.snapshot()
        blocker = self.board.blocker_of(arrow)
        result = self.board.click(row, col)

        if result is ClickResult.FLY_OUT:
            self.history.append(snapshot)
            self.flying.append(
                FlyOutAnimation(
                    self.cell_center(row, col),
                    arrow.direction,
                    self.cell_size,
                    (config.WINDOW_WIDTH, config.WINDOW_HEIGHT),
                    ui.draw_arrow_color(arrow.direction),
                )
            )
            self._on_board_changed()

        elif result is ClickResult.BLOCKED:
            self.history.append(snapshot)
            self.shaking[(row, col)] = ShakeAnimation(
                self.cell_center(row, col),
                arrow.direction,
                self.cell_size,
                ui.draw_arrow_color(arrow.direction),
            )
            if blocker is not None:
                self.highlights.append(
                    HighlightAnimation(
                        self.cell_center(blocker.row, blocker.col), self.cell_size
                    )
                )
            self.toast = Toast(
                f"前方有阻挡！剩余失误 {self.board.misses_left} 次",
                config.COLOR_DANGER,
            )
            self._on_board_changed()

    def _on_board_changed(self) -> None:
        """棋盘状态变化后检查本关是否已经分出胜负。"""
        if self.board.state is GameState.WIN:
            self.exit_timer = 0.75
        elif self.board.state is GameState.LOSE:
            self.exit_timer = 0.95

    def restart(self) -> None:
        """把本关恢复到初始状态（对应测试 T06）。"""
        self.board.reset()
        self.play_time = 0.0
        self.history.clear()
        self.flying.clear()
        self.shaking.clear()
        self.highlights.clear()
        self.toast = None
        self.exit_timer = None

    def undo(self) -> None:
        """撤销上一步：把棋盘、失误数一起退回去。"""
        if not self.history or self.board.is_over:
            return
        self.board.restore(self.history.pop())
        self.flying.clear()
        self.shaking.clear()
        self.highlights.clear()
        self.toast = Toast("已撤销上一步", config.COLOR_TEXT_DIM)

    def use_hint(self) -> None:
        """高亮一个当前可以飞出的箭头。

        每次取下一个（而不是永远取第一个），连点提示能依次看遍所有可选项。
        """
        if self.board.is_over:
            return
        free = self.board.free_arrows()
        if not free:
            self.toast = Toast("已经没有任何箭头能飞出了", config.COLOR_DANGER)
            return

        arrow = free[self.hint_rotation % len(free)]
        self.hint_rotation = (self.hint_rotation + 1) % len(free)
        self.highlights.append(
            HighlightAnimation(
                self.cell_center(arrow.row, arrow.col),
                self.cell_size,
                config.COLOR_SUCCESS,
            )
        )
        self.toast = Toast(
            f"提示：({arrow.row + 1},{arrow.col + 1}) 处的箭头可以飞出",
            config.COLOR_SUCCESS,
        )

    # ------------------------------------------------------------ 更新

    def update(self, dt: float) -> None:
        if self.board.state is GameState.PLAYING:
            self.play_time += dt

        for animation in self.flying:
            animation.update(dt)
        self.flying = [a for a in self.flying if not a.finished]

        for cell in list(self.shaking):
            animation = self.shaking[cell]
            animation.update(dt)
            if animation.finished:
                del self.shaking[cell]

        for animation in self.highlights:
            animation.update(dt)
        self.highlights = [a for a in self.highlights if not a.finished]

        if self.toast is not None:
            self.toast.update(dt)
            if self.toast.finished:
                self.toast = None

        if self.exit_timer is not None:
            self.exit_timer -= dt
            if self.exit_timer <= 0:
                self.exit_timer = None
                self.app.show_result(self, self.board.state is GameState.WIN)

        # 提示 / 撤销在关卡结束后没有意义，置灰
        over = self.board.is_over
        self.buttons[0].enabled = not over   # 提示
        self.buttons[1].enabled = bool(self.history) and not over   # 撤销

    # ------------------------------------------------------------ 绘制

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(config.COLOR_BG)
        self.draw_hud(surface)
        self.draw_toast(surface)
        self.draw_board(surface)
        self.draw_footer(surface)
        for button in self.buttons:
            button.draw(surface)

    def draw_board(self, surface: pygame.Surface, animations: bool = True) -> None:
        board_w = self.cell_size * self.board.cols
        board_h = self.cell_size * self.board.rows
        ox, oy = self.board_origin

        backdrop = pygame.Rect(ox - 12, oy - 12, board_w + 24, board_h + 24)
        ui.draw_panel(surface, backdrop, config.COLOR_BOARD_BG, radius=14)

        for row in range(self.board.rows):
            for col in range(self.board.cols):
                rect = self.cell_rect(row, col).inflate(-6, -6)
                ui.draw_panel(
                    surface, rect, config.COLOR_CELL, config.COLOR_CELL_EDGE, radius=10
                )

        if not animations:
            self._draw_arrows(surface, skip_cells=set())
            return

        for animation in self.highlights:
            animation.draw(surface)

        # 正在抖动的箭头由抖动动画自己画，这里跳过，避免画成两个
        self._draw_arrows(surface, skip_cells=set(self.shaking))

        for animation in self.shaking.values():
            animation.draw(surface)
        for animation in self.flying:
            animation.draw(surface)

    def _draw_arrows(self, surface: pygame.Surface, skip_cells: set) -> None:
        for cell, arrow in self.board.arrows.items():
            if cell in skip_cells:
                continue
            ui.draw_arrow(
                surface,
                self.cell_center(arrow.row, arrow.col),
                self.cell_size,
                arrow.direction,
                ui.draw_arrow_color(arrow.direction),
            )

    def draw_hud(self, surface: pygame.Surface) -> None:
        hud_rect = pygame.Rect(0, 0, config.WINDOW_WIDTH, config.HUD_HEIGHT)
        pygame.draw.rect(surface, config.COLOR_HUD_BG, hud_rect)

        ui.draw_text(
            surface,
            self.level.name,
            (config.BOARD_AREA_SIDE_MARGIN, 26),
            config.FONT_SIZE_NORMAL,
            config.COLOR_TEXT,
            bold=True,
        )

        # 三项统计：剩余箭头 / 剩余失误 / 用时
        remain = self.board.remaining
        total = self.board.total_arrows
        misses = self.board.misses_left
        miss_color = config.COLOR_DANGER if misses <= 1 else config.COLOR_TEXT

        stats = [
            ("剩余箭头", f"{remain} / {total}", config.COLOR_TEXT),
            ("剩余失误", f"{misses} 次", miss_color),
            ("用时", format_time(self.play_time), config.COLOR_TEXT),
        ]
        # 三栏的标签宽度不同（「用时」比「剩余箭头」短得多），
        # 如果按固定偏移摆数值，各栏的间距就会参差不齐。这里取最宽的标签
        # 作为统一偏移，让三个数值左边缘对齐。
        value_offset = (
            max(ui.text_size(label, config.FONT_SIZE_SMALL)[0] for label, _, _ in stats)
            + 14
        )
        for index, (label, value, color) in enumerate(stats):
            x = config.BOARD_AREA_SIDE_MARGIN + index * 200
            ui.draw_text(
                surface, label, (x, 74), config.FONT_SIZE_SMALL, config.COLOR_TEXT_DIM
            )
            ui.draw_text(
                surface, value, (x + value_offset, 72), config.FONT_SIZE_NORMAL,
                color, bold=True,
            )

        # 清关进度条：横贯信息栏底部
        bar = pygame.Rect(
            config.BOARD_AREA_SIDE_MARGIN,
            config.HUD_HEIGHT - 12,
            config.WINDOW_WIDTH - 2 * config.BOARD_AREA_SIDE_MARGIN,
            6,
        )
        cleared_ratio = 1.0 - (remain / total) if total else 0.0
        ui.draw_progress_bar(surface, bar, cleared_ratio, config.COLOR_SUCCESS)

    def draw_toast(self, surface: pygame.Surface) -> None:
        if self.toast is None:
            return
        ui.draw_text(
            surface,
            self.toast.text,
            (config.WINDOW_WIDTH // 2, config.HUD_HEIGHT + config.TOAST_HEIGHT // 2),
            config.FONT_SIZE_SMALL,
            self.toast.color,
            anchor="center",
            alpha=self.toast.alpha(),
        )

    def draw_footer(self, surface: pygame.Surface) -> None:
        ui.draw_text(
            surface,
            "左键点击箭头飞出　|　R 重新开始　H 提示　Z 撤销　ESC 返回主菜单",
            (config.WINDOW_WIDTH // 2, config.WINDOW_HEIGHT - 26),
            config.FONT_SIZE_SMALL,
            config.COLOR_TEXT_DIM,
            anchor="center",
        )


# ======================================================================
# 结果界面
# ======================================================================


class ResultScene(Scene):
    """通关 / 失败结算。棋盘保留在背景里，上面盖一层半透明遮罩。"""

    def __init__(self, app: "App", play: PlayScene, won: bool) -> None:
        self.app = app
        self.play = play
        self.won = won
        self.moves = play.board.cleared + (play.board.max_misses - play.board.misses_left)

        self.buttons: List[ui.Button] = []
        center_x = config.WINDOW_WIDTH // 2
        y = 452

        # 通关时多一个「下一关」；按钮数量会变，按实际宽度整体居中
        specs = []
        if won and play.level_index + 1 < len(LEVELS):
            specs.append(("下一关", 150, self._next_level))
        specs.append(("重玩本关", 160, self._replay))
        specs.append(("返回主菜单", 150, self.app.go_start))

        gap = 20
        total_width = sum(width for _, width, _ in specs) + gap * (len(specs) - 1)
        x = center_x - total_width // 2
        for text, width, callback in specs:
            self.buttons.append(
                ui.Button(
                    (x, y, width, 52),
                    text,
                    callback,
                    font_size=config.FONT_SIZE_NORMAL,
                )
            )
            x += width + gap

    def _next_level(self) -> None:
        self.app.start_level(self.play.level_index + 1)

    def _replay(self) -> None:
        self.app.start_level(self.play.level_index)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.app.go_start()
            elif event.key == pygame.K_r:
                self._replay()
            elif event.key == pygame.K_RETURN and self.won:
                if self.play.level_index + 1 < len(LEVELS):
                    self._next_level()
            return
        for button in self.buttons:
            button.handle_event(event)

    def draw(self, surface: pygame.Surface) -> None:
        # 先画出结算前的棋盘，让玩家能看到最后一手的结果
        surface.fill(config.COLOR_BG)
        self.play.draw_hud(surface)
        self.play.draw_board(surface, animations=False)

        overlay = pygame.Surface((config.WINDOW_WIDTH, config.WINDOW_HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 12, 20, 205))
        surface.blit(overlay, (0, 0))

        center_x = config.WINDOW_WIDTH // 2
        panel = pygame.Rect(center_x - 290, 168, 580, 400)
        ui.draw_panel(surface, panel, config.COLOR_HUD_BG, config.COLOR_CELL_EDGE, radius=18)

        if self.won:
            title, title_color = "通 关 ！", config.COLOR_SUCCESS
            subtitle = "全部箭头都已飞出棋盘"
        else:
            title, title_color = "挑 战 失 败", config.COLOR_DANGER
            subtitle = "失误次数已用尽，再来一次吧"

        ui.draw_text(
            surface, title, (center_x, 232), config.FONT_SIZE_TITLE, title_color,
            anchor="center", bold=True,
        )
        ui.draw_text(
            surface, subtitle, (center_x, 292), config.FONT_SIZE_NORMAL,
            config.COLOR_TEXT_DIM, anchor="center",
        )
        ui.draw_text(
            surface, self.play.level.name, (center_x, 336), config.FONT_SIZE_NORMAL,
            config.COLOR_TEXT, anchor="center", bold=True,
        )

        stats = [
            f"用时 {format_time(self.play.play_time)}",
            f"点击 {self.moves} 次",
            f"剩余失误 {self.play.board.misses_left} 次",
        ]
        for index, text in enumerate(stats):
            x = center_x - 170 + index * 170
            ui.draw_text(
                surface, text, (x, 386), config.FONT_SIZE_SMALL,
                config.COLOR_TEXT, anchor="center",
            )

        for button in self.buttons:
            button.draw(surface)


# ======================================================================
# 应用主体
# ======================================================================


class App:
    """持有窗口、主循环与全局进度。"""

    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption(config.WINDOW_TITLE)
        self.screen = pygame.display.set_mode(
            (config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
        )
        self.clock = pygame.time.Clock()
        self.running = True

        self.unlocked = 1                      # 已解锁的关卡数
        self.records: Dict[int, Tuple[float, int]] = {}   # 关卡下标 -> (用时, 点击数)
        self.scene: Scene = StartScene(self)

    # ------------------------------------------------------------ 场景切换

    def set_scene(self, scene: Scene) -> None:
        self.scene = scene

    def go_start(self) -> None:
        self.set_scene(StartScene(self))

    def start_level(self, level_index: int) -> None:
        self.set_scene(PlayScene(self, level_index))

    def start_new_game(self) -> None:
        """从最早还没通关的关卡开始；全部通关了就从头再来。"""
        index = self.unlocked - 1
        if index >= len(LEVELS):
            index = 0
        self.start_level(index)

    def show_result(self, play: PlayScene, won: bool) -> None:
        if won:
            self.unlocked = min(len(LEVELS), max(self.unlocked, play.level_index + 2))
            moves = play.board.cleared + (
                play.board.max_misses - play.board.misses_left
            )
            previous = self.records.get(play.level_index)
            if previous is None or play.play_time < previous[0]:
                self.records[play.level_index] = (play.play_time, moves)
        self.set_scene(ResultScene(self, play, won))

    def quit(self) -> None:
        self.running = False

    # ------------------------------------------------------------ 主循环

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(config.FPS) / 1000.0
            # 窗口拖动等情况会让某一帧特别长，钳一下避免动画瞬移
            dt = min(dt, 0.05)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                else:
                    self.scene.handle_event(event)

            self.scene.update(dt)
            self.scene.draw(self.screen)
            pygame.display.flip()

        pygame.quit()
