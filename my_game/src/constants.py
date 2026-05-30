"""
src/constants.py — 全局常量与默认值
"""

MODEL_BASE = "assets/models"
SFX_BASE = "assets/sounds"

# 物理默认参数
DEFAULTS = {
    "gravity": -9.81,
    "player_mass": 5.0,
    "player_friction": 1.0,
    "player_restitution": 0.0,
    "box_mass": 1.0,
    "box_friction": 0.8,
    "box_restitution": 0.4,
    "ground_friction": 1.0,
    "ground_restitution": 0.3,
    "jump_force": 6.0,
    "sfx_volume": 0.7,
}

# ── 可拾取经验方块 ──
GEM_SPAWN_INTERVAL = 3.0        # 每隔 N 秒尝试生成一个
GEM_MAX_COUNT = 15              # 场景中最多同时存在的数量
GEM_SPAWN_RANGE_X = (-15, 15)   # 生成范围 X
GEM_SPAWN_RANGE_Y = (0, 40)     # 生成范围 Y
GEM_SPAWN_HEIGHT = 5.0          # 生成高度（会落下来）
GEM_EXP_MIN = 1                 # 最小经验值
GEM_EXP_MAX = 10                # 最大经验值
GEM_COLLECT_DISTANCE = 2.5      # 玩家自动拾取距离

# 相机默认参数
CAM_HEADING = 180.0
CAM_PITCH = -15.0
CAM_DISTANCE = 25.0
CAM_PITCH_MIN = -80.0
CAM_PITCH_MAX = 10.0
CAM_DIST_MIN = 5.0
CAM_DIST_MAX = 80.0
CAM_MOUSE_SENSITIVITY = 0.3

# 玩家移动速度
PLAYER_SPEED = 8.0

# macOS 中文字体候选路径
CJK_FONT_CANDIDATES = [
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
]
