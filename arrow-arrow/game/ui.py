"""绘制工具：中文字体加载、箭头多边形、按钮。"""

from __future__ import annotations

import math
import os
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import pygame

from . import config
from .board import Direction

Color = Tuple[int, int, int]
Point = Tuple[float, float]


# ------------------------------------------------------------------
# 字体
# ------------------------------------------------------------------

#: 字体对象开销不小，按 (字号, 是否粗体) 缓存，避免每帧重复加载
_font_cache: Dict[Tuple[int, bool], pygame.font.Font] = {}


def _first_existing(paths: Sequence[str]) -> Optional[str]:
    for path in paths:
        if os.path.exists(path):
            return path
    return None


def get_font(size: int, bold: bool = False) -> pygame.font.Font:
    """加载中文字体。

    pygame 的默认字体不含中文字形，直接拿来渲染中文会得到一排方块（豆腐块）。
    所以这里显式去加载系统里的中文字体文件；万一一个都找不到，
    再退回 SysFont 按字体名碰运气，至少不至于崩掉。
    """
    key = (size, bold)
    cached = _font_cache.get(key)
    if cached is not None:
        return cached

    candidates = config.FONT_BOLD_CANDIDATES if bold else config.FONT_REGULAR_CANDIDATES
    path = _first_existing(candidates)
    if path:
        font = pygame.font.Font(path, size)
    else:
        font = pygame.font.SysFont("microsoftyahei,simhei,simsun,arial", size, bold=bold)

    _font_cache[key] = font
    return font


def text_size(text: str, size: int, bold: bool = False) -> Tuple[int, int]:
    """量一段文字渲染后的宽高，用于对齐排版。"""
    return get_font(size, bold).size(text)


def draw_text(
    surface: pygame.Surface,
    text: str,
    pos: Point,
    size: int = config.FONT_SIZE_NORMAL,
    color: Color = config.COLOR_TEXT,
    anchor: str = "topleft",
    bold: bool = False,
    alpha: int = 255,
) -> pygame.Rect:
    """绘制一行文字，返回它占据的矩形。

    ``alpha`` 用于提示条这类需要淡出的文字 —— 字体渲染出来的表面
    本身带 alpha 通道，直接 ``set_alpha`` 会覆盖掉抗锯齿的边缘，
    所以只在需要半透明时才动它。
    """
    image = get_font(size, bold).render(text, True, color)
    if alpha < 255:
        image.set_alpha(alpha)
    rect = image.get_rect(**{anchor: pos})
    surface.blit(image, rect)
    return rect


# ------------------------------------------------------------------
# 箭头
# ------------------------------------------------------------------

#: 朝右的箭头轮廓，单位是「格子边长的倍数」，后续按方向整体旋转。
#: 分成箭杆（矩形）和箭头（三角形）两段，拼成一个规整的箭头形状。
_ARROW_OUTLINE: List[Point] = [
    (-0.34, -0.10),   # 箭杆左上
    (0.04, -0.10),    # 箭杆右上
    (0.04, -0.26),    # 箭头左上角
    (0.34, 0.00),     # 箭尖
    (0.04, 0.26),     # 箭头左下角
    (0.04, 0.10),     # 箭杆右下
    (-0.34, 0.10),    # 箭杆左下
]

#: 把「朝右」旋转到各个方向所需的角度（度），屏幕坐标 y 轴向下
_DIRECTION_ANGLE = {
    Direction.RIGHT: 0,
    Direction.DOWN: 90,
    Direction.LEFT: 180,
    Direction.UP: 270,
}


def arrow_polygon(
    center: Point,
    size: float,
    direction: Direction,
    scale: float = 1.0,
) -> List[Point]:
    """算出箭头多边形的顶点坐标。"""
    angle = math.radians(_DIRECTION_ANGLE[direction])
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    cx, cy = center

    points: List[Point] = []
    for fx, fy in _ARROW_OUTLINE:
        x, y = fx * size * scale, fy * size * scale
        points.append((cx + x * cos_a - y * sin_a, cy + x * sin_a + y * cos_a))
    return points


def _shade(color: Color, factor: float) -> Color:
    """把颜色调暗（factor < 1）或调亮（factor > 1）。"""
    return tuple(max(0, min(255, int(channel * factor))) for channel in color)  # type: ignore[return-value]


def draw_arrow(
    surface: pygame.Surface,
    center: Point,
    size: float,
    direction: Direction,
    color: Color,
    alpha: int = 255,
    scale: float = 1.0,
) -> None:
    """在 ``center`` 处画一个箭头。

    ``alpha`` 小于 255 时走临时透明表面再整体贴图 —— pygame 的
    ``draw.polygon`` 本身不支持透明度，必须借助 SRCALPHA 表面。
    """
    points = arrow_polygon(center, size, direction, scale)

    if alpha >= 255:
        pygame.draw.polygon(surface, color, points)
        pygame.draw.polygon(surface, _shade(color, 0.65), points, width=2)
        return

    pad = int(size) + 4
    temp = pygame.Surface((pad * 2, pad * 2), pygame.SRCALPHA)
    local = [(x - center[0] + pad, y - center[1] + pad) for x, y in points]
    pygame.draw.polygon(temp, (*color, alpha), local)
    surface.blit(temp, (center[0] - pad, center[1] - pad))


def draw_arrow_color(direction: Direction, collided: bool = False) -> Color:
    """箭头颜色：正常情况下按方向区分，碰撞瞬间统一变红。"""
    if collided:
        return config.COLOR_BLOCKED
    return config.COLOR_ARROW[direction.name]


# ------------------------------------------------------------------
# 按钮
# ------------------------------------------------------------------


class Button:
    """一个矩形按钮。``on_click`` 在按下鼠标左键时调用。"""

    def __init__(
        self,
        rect: Sequence[int],
        text: str,
        on_click: Callable[[], None],
        *,
        font_size: int = config.FONT_SIZE_NORMAL,
        enabled: bool = True,
    ) -> None:
        self.rect = pygame.Rect(rect)
        self.text = text
        self.on_click = on_click
        self.font_size = font_size
        self.enabled = enabled
        self.hovered = False

    def handle_event(self, event: pygame.event.Event) -> bool:
        """处理一个事件，返回是否被点击。"""
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.enabled and self.rect.collidepoint(event.pos)
        elif (
            event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
            and self.enabled
            and self.rect.collidepoint(event.pos)
        ):
            self.on_click()
            return True
        return False

    def draw(self, surface: pygame.Surface) -> None:
        if not self.enabled:
            fill = config.COLOR_BUTTON_DISABLED
            text_color = _shade(config.COLOR_BUTTON_TEXT, 0.45)
        elif self.hovered:
            fill = config.COLOR_BUTTON_HOVER
            text_color = config.COLOR_TEXT
        else:
            fill = config.COLOR_BUTTON
            text_color = config.COLOR_BUTTON_TEXT

        pygame.draw.rect(surface, fill, self.rect, border_radius=8)
        draw_text(
            surface,
            self.text,
            self.rect.center,
            self.font_size,
            text_color,
            anchor="center",
        )


# ------------------------------------------------------------------
# 杂项
# ------------------------------------------------------------------


def draw_panel(
    surface: pygame.Surface,
    rect: pygame.Rect,
    fill: Color,
    border: Optional[Color] = None,
    radius: int = 10,
    border_width: int = 2,
) -> None:
    """画一个圆角面板。"""
    pygame.draw.rect(surface, fill, rect, border_radius=radius)
    if border is not None:
        pygame.draw.rect(surface, border, rect, width=border_width, border_radius=radius)


def draw_progress_bar(
    surface: pygame.Surface,
    rect: pygame.Rect,
    ratio: float,
    color: Color,
    track: Color = config.COLOR_CELL,
) -> None:
    """画一条进度条，``ratio`` 取值 0~1。"""
    ratio = max(0.0, min(1.0, ratio))
    pygame.draw.rect(surface, track, rect, border_radius=rect.height // 2)
    if ratio > 0:
        filled = pygame.Rect(rect.x, rect.y, max(rect.height, int(rect.width * ratio)), rect.height)
        pygame.draw.rect(surface, color, filled, border_radius=rect.height // 2)
