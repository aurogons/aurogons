"""全局配置：窗口尺寸、布局、配色、字体与动画时长。

手感相关和外观相关的可调参数都集中在这里，改这些不用翻业务代码。
"""

# ---------------------------------------------------------------- 窗口

WINDOW_WIDTH = 900
WINDOW_HEIGHT = 720
WINDOW_TITLE = "一箭又一箭"
FPS = 60

# ---------------------------------------------------------------- 布局

HUD_HEIGHT = 118           # 顶部信息栏高度
TOAST_HEIGHT = 36          # 信息栏下方的提示条高度
BOARD_AREA_TOP = HUD_HEIGHT + TOAST_HEIGHT + 8
BOARD_AREA_BOTTOM_MARGIN = 46
BOARD_AREA_SIDE_MARGIN = 40

MAX_CELL_SIZE = 96         # 格子最大边长（小棋盘时格子更大，更好点）
MIN_CELL_SIZE = 48         # 格子最小边长（防止大棋盘挤爆窗口）

# ---------------------------------------------------------------- 配色

COLOR_BG = (24, 26, 36)            # 窗口背景
COLOR_HUD_BG = (33, 36, 49)        # 顶部信息栏
COLOR_CELL = (45, 50, 66)          # 棋盘格底色
COLOR_CELL_EDGE = (58, 64, 84)     # 棋盘格描边
COLOR_BOARD_BG = (30, 33, 45)      # 棋盘外框

COLOR_TEXT = (232, 236, 246)       # 主要文字
COLOR_TEXT_DIM = (146, 154, 176)   # 次要文字

# 四个方向各用一种颜色，玩家扫一眼就能分清朝向。
# 刻意避开红色系，把红色留给碰撞反馈，避免误解。
COLOR_ARROW = {
    "UP": (255, 200, 87),          # 琥珀
    "DOWN": (109, 213, 160),       # 青绿
    "LEFT": (110, 168, 254),       # 天蓝
    "RIGHT": (196, 148, 255),      # 淡紫
}

COLOR_BLOCKED = (255, 92, 92)      # 碰撞瞬间的红色
COLOR_HIGHLIGHT = (255, 236, 140)  # 提示 / 挡路箭头高亮
COLOR_SUCCESS = (109, 213, 160)
COLOR_DANGER = (255, 108, 108)

COLOR_BUTTON = (58, 66, 92)
COLOR_BUTTON_HOVER = (78, 88, 120)
COLOR_BUTTON_TEXT = (232, 236, 246)
COLOR_BUTTON_DISABLED = (46, 50, 64)

# ---------------------------------------------------------------- 动画

FLY_OUT_DURATION = 0.28    # 箭头飞出耗时（秒）
SHAKE_DURATION = 0.40      # 碰撞抖动耗时（秒）
SHAKE_AMPLITUDE = 8        # 抖动幅度（像素）
SHAKE_FREQUENCY = 3.2      # 抖动来回次数
HIGHLIGHT_DURATION = 0.9   # 挡路箭头 / 提示箭头的高亮持续时间
TOAST_DURATION = 1.1       # 提示条文字停留时间

# ---------------------------------------------------------------- 字体

# pygame 自带字体渲染中文会变成方块，必须显式加载中文字体。
# 按优先级依次尝试，第一个存在的会被用上。
FONT_REGULAR_CANDIDATES = [
    "C:/Windows/Fonts/msyh.ttc",      # 微软雅黑
    "C:/Windows/Fonts/simhei.ttf",    # 黑体
    "C:/Windows/Fonts/simsun.ttc",    # 宋体
]
FONT_BOLD_CANDIDATES = [
    "C:/Windows/Fonts/msyhbd.ttc",    # 微软雅黑 粗体
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/msyh.ttc",
]

FONT_SIZE_TITLE = 58
FONT_SIZE_HEADING = 34
FONT_SIZE_NORMAL = 22
FONT_SIZE_SMALL = 18
