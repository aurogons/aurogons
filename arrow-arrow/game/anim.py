"""动画对象：飞出、碰撞抖动、高亮。

设计要点：**动画只负责「画什么」，不参与任何规则判定。**

点击发生时棋盘状态立刻更新，飞出动画只是一个与棋盘无关的视觉残影。
好处是输入永远不需要等待动画播完 —— 玩家可以连着快速点，
也不会出现「上一次动画还没结束就点下一发」的竞态。
如果改成「动画期间锁住输入」，每次点击都得等 0.3 秒才能点下一个，手感会明显发滞。
"""

from __future__ import annotations

import math
from typing import Tuple

import pygame

from . import config
from .board import Direction
from .ui import Color, Point, draw_arrow, draw_arrow_color

#: 让抖动 / 闪烁的相位计算好看一点
_TAU = math.tau


class FlyOutAnimation:
    """箭头沿自身方向滑出窗口，后半程逐渐淡出。"""

    def __init__(
        self,
        center: Point,
        direction: Direction,
        cell_size: float,
        window_size: Tuple[int, int],
        color: Color,
        duration: float = config.FLY_OUT_DURATION,
    ) -> None:
        self.center = center
        self.direction = direction
        self.cell_size = cell_size
        self.color = color
        self.duration = duration
        self.elapsed = 0.0

        drow, dcol = direction.delta
        # 棋盘坐标 -> 屏幕坐标：col 对应 x，row 对应 y
        self.dx, self.dy = float(dcol), float(drow)
        self.distance = self._distance_to_leave(window_size)

    def _distance_to_leave(self, window_size: Tuple[int, int]) -> float:
        """从起点沿方向走到完全离开窗口所需的距离。"""
        cx, cy = self.center
        if self.dx > 0:
            return window_size[0] - cx + self.cell_size
        if self.dx < 0:
            return cx + self.cell_size
        if self.dy > 0:
            return window_size[1] - cy + self.cell_size
        return cy + self.cell_size

    @property
    def progress(self) -> float:
        return min(1.0, self.elapsed / self.duration)

    @property
    def finished(self) -> bool:
        return self.elapsed >= self.duration

    def update(self, dt: float) -> None:
        self.elapsed += dt

    def draw(self, surface: pygame.Surface) -> None:
        progress = self.progress
        center = (
            self.center[0] + self.dx * self.distance * progress,
            self.center[1] + self.dy * self.distance * progress,
        )
        # 前 35% 保持不透明（让玩家看清是哪个箭头飞了），之后线性淡出
        fade = max(0.0, 1.0 - max(0.0, progress - 0.35) / 0.65)
        alpha = int(255 * fade)
        draw_arrow(
            surface, center, self.cell_size, self.direction, self.color, alpha=alpha
        )


class ShakeAnimation:
    """碰撞反馈：箭头原地抖动 + 变红闪烁 + 轻微放大。

    抖动方向取**垂直于箭头朝向**的那一轴：横着的箭头上下抖，竖着的左右抖。
    之所以不顺着箭头方向抖，是因为那样看起来像「飞出动画卡了一下」，
    垂直抖动才能明确表达「被挡回来了」。
    """

    def __init__(
        self,
        center: Point,
        direction: Direction,
        cell_size: float,
        base_color: Color,
        duration: float = config.SHAKE_DURATION,
    ) -> None:
        self.center = center
        self.direction = direction
        self.cell_size = cell_size
        self.base_color = base_color
        self.duration = duration
        self.elapsed = 0.0

        # 垂直于朝向的抖动轴
        if direction in (Direction.LEFT, Direction.RIGHT):
            self.axis = (0.0, 1.0)
        else:
            self.axis = (1.0, 0.0)

    @property
    def progress(self) -> float:
        return min(1.0, self.elapsed / self.duration)

    @property
    def finished(self) -> bool:
        return self.elapsed >= self.duration

    def update(self, dt: float) -> None:
        self.elapsed += dt

    def _phase(self) -> float:
        return _TAU * config.SHAKE_FREQUENCY * self.progress

    def offset(self) -> Point:
        """当前的抖动偏移量。振幅随时间衰减，抖到后面自然停下。"""
        decay = 1.0 - self.progress
        amount = config.SHAKE_AMPLITUDE * decay * math.sin(self._phase())
        return (self.axis[0] * amount, self.axis[1] * amount)

    def current_color(self) -> Color:
        """在箭头本色与警示红之间闪烁，以红色为主。"""
        return config.COLOR_BLOCKED if math.sin(self._phase()) > -0.25 else self.base_color

    def draw(self, surface: pygame.Surface) -> None:
        dx, dy = self.offset()
        center = (self.center[0] + dx, self.center[1] + dy)
        scale = 1.0 + 0.12 * (1.0 - self.progress)
        draw_arrow(
            surface,
            center,
            self.cell_size,
            self.direction,
            self.current_color(),
            scale=scale,
        )


class HighlightAnimation:
    """给某个箭头套一圈脉冲高亮。

    两种用途：点击被挡住时高亮「是谁挡的路」，以及「提示」功能
    标出一个当前可以飞出的箭头。
    """

    def __init__(
        self,
        center: Point,
        cell_size: float,
        color: Color = config.COLOR_HIGHLIGHT,
        duration: float = config.HIGHLIGHT_DURATION,
    ) -> None:
        self.center = center
        self.cell_size = cell_size
        self.color = color
        self.duration = duration
        self.elapsed = 0.0

    @property
    def progress(self) -> float:
        return min(1.0, self.elapsed / self.duration)

    @property
    def finished(self) -> bool:
        return self.elapsed >= self.duration

    def update(self, dt: float) -> None:
        self.elapsed += dt

    def draw(self, surface: pygame.Surface) -> None:
        # 呼吸式脉冲：亮 -> 暗 -> 亮，最后整体淡出
        pulse = 0.55 + 0.45 * math.sin(_TAU * 2.0 * self.progress)
        fade = 1.0 - self.progress
        alpha = int(190 * pulse * fade)
        if alpha <= 0:
            return

        pad = self.cell_size * 0.5
        rect = pygame.Rect(0, 0, int(pad * 2), int(pad * 2))
        rect.center = (int(self.center[0]), int(self.center[1]))

        overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(
            overlay,
            (*self.color, alpha),
            overlay.get_rect(),
            width=3,
            border_radius=10,
        )
        surface.blit(overlay, rect.topleft)


class Toast:
    """一条会在若干秒后自动消失的提示文字。"""

    def __init__(self, text: str, color: Color, duration: float = config.TOAST_DURATION) -> None:
        self.text = text
        self.color = color
        self.duration = duration
        self.elapsed = 0.0

    @property
    def finished(self) -> bool:
        return self.elapsed >= self.duration

    def update(self, dt: float) -> None:
        self.elapsed += dt

    def alpha(self) -> int:
        """最后 35% 的时间里淡出。"""
        progress = self.elapsed / self.duration
        fade = max(0.0, 1.0 - max(0.0, progress - 0.65) / 0.35)
        return int(255 * fade)
