"""
src/constants.py — 全局常量与默认值
====================================
所有可调参数集中管理，按功能分组。
修改此文件即可调整游戏行为，无需改动逻辑代码。
"""

# ══════════════════════════════════════════════════════════════
# 资源路径
# ══════════════════════════════════════════════════════════════
MODEL_BASE = "assets/models"    # 模型文件根目录
SFX_BASE = "assets/sounds"      # 音效文件根目录

# ══════════════════════════════════════════════════════════════
# 物理引擎参数（Bullet）
# ══════════════════════════════════════════════════════════════
DEFAULTS = {
    # 世界
    "gravity": -9.81,            # 重力加速度 (m/s²)

    # 玩家物理体
    "player_mass": 5.0,          # 质量 (kg)
    "player_friction": 1.0,      # 摩擦系数
    "player_restitution": 0.0,   # 弹性系数（0=不弹跳）
    "jump_force": 6.0,           # 跳跃初速度 (m/s)

    # 动态方块
    "box_mass": 1.0,
    "box_friction": 0.8,
    "box_restitution": 0.4,

    # 地面
    "ground_friction": 1.0,
    "ground_restitution": 0.3,

    # 音效
    "sfx_volume": 0.7,           # 全局音效音量 (0.0–1.0)
}

# ══════════════════════════════════════════════════════════════
# 玩家参数
# ══════════════════════════════════════════════════════════════
PLAYER_SPEED = 8.0               # 移动速度 (单位/秒)

# ══════════════════════════════════════════════════════════════
# 相机参数
# ══════════════════════════════════════════════════════════════
CAM_HEADING = 180.0              # 初始 heading（度）
CAM_PITCH = -15.0                # 初始 pitch（度）
CAM_DISTANCE = 25.0              # 轨道模式初始距离
CAM_PITCH_MIN = -80.0            # pitch 下限
CAM_PITCH_MAX = 10.0             # pitch 上限
CAM_DIST_MIN = 5.0               # 轨道模式最小距离
CAM_DIST_MAX = 80.0              # 轨道模式最大距离
CAM_MOUSE_SENSITIVITY = 0.3      # 鼠标灵敏度

# ══════════════════════════════════════════════════════════════
# 可拾取经验方块
# ══════════════════════════════════════════════════════════════
GEM_SPAWN_INTERVAL = 3.0         # 生成间隔（秒）
GEM_MAX_COUNT = 15               # 场景中最大同时存在数量
GEM_SPAWN_RANGE_X = (-15, 15)    # 生成范围 X 轴
GEM_SPAWN_RANGE_Y = (0, 40)      # 生成范围 Y 轴
GEM_SPAWN_HEIGHT = 5.0           # 生成高度（会自由落体）
GEM_EXP_MIN = 1                  # 最小经验值
GEM_EXP_MAX = 10                 # 最大经验值
GEM_COLLECT_DISTANCE = 2.5       # 自动拾取距离（单位）

# ══════════════════════════════════════════════════════════════
# 中文字体（macOS 系统字体候选路径）
# ══════════════════════════════════════════════════════════════
CJK_FONT_CANDIDATES = [
    "/System/Library/Fonts/STHeiti Medium.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/System/Library/Fonts/Supplemental/Songti.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
]
