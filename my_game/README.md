# 🎮 My Panda3D Game — Mac 开发模板

> **当前版本：v0.5.0** · 2026-05-30

基于 **Panda3D 1.11.0 + Python 3.13** 的 macOS 游戏开发起点模板。

集成 **Bullet 物理引擎**、**跳跃系统**、**音效系统**、**鼠标拾取交互**、**轨道相机**、**中文字体**、**设置面板（调试 + 物理参数 Tab）**、**经验值系统**。

---

## 环境要求

| 工具 | 版本 | 安装方式 |
|------|------|---------|
| macOS | 12 Monterey+ | — |
| Python | 3.13 | [python.org](https://www.python.org/) |
| Panda3D SDK | 1.11.0 | `Panda3D-1.11.0-py3.13.dmg` 或 `pip install panda3d` |

> 工作区根目录已包含 `Panda3D-1.11.0-py3.13.dmg`，双击安装即可。

---

## 项目目录结构

```
my_game/
├── main.py                  # 游戏入口（~170 行，组合各子系统）
├── config.prc               # Panda3D 运行时配置
├── README.md                # 本文档
├── src/                     # 子模块包
│   ├── __init__.py
│   ├── constants.py         # 全局常量 & 默认参数
│   ├── physics.py           # Bullet 物理引擎管理
│   ├── player.py            # 玩家控制（移动 + 跳跃 + 地面检测 + 经验值）
│   ├── camera.py            # 轨道相机
│   ├── audio.py             # 音效系统
│   ├── picking.py           # 鼠标拾取交互（含经验方块点击拾取）
│   ├── collectibles.py      # 可拾取经验方块生成与管理
│   ├── scene.py             # 场景构建（地面 + 障碍物 + 光照）
│   ├── hud.py               # HUD 信息 + 中文字体 + 经验值显示
│   └── settings_panel.py    # 设置面板（Tab 切换 + 滑块）
└── assets/
    ├── models/              # .egg.pz 3D 模型 + maps/ 贴图
    │   ├── environment.egg.pz
    │   ├── panda-model.egg.pz
    │   ├── panda-walk4.egg.pz
    │   ├── box.egg.pz
    │   └── maps/            # 模型贴图文件
    └── sounds/              # .wav 音效
        ├── GUI_click.wav
        └── GUI_rollover.wav
```

---

## 快速启动

```bash
# 进入游戏目录
cd /Users/mac/code/panda3d-master/my_game

# 运行游戏
python3 main.py
```

---

## 操作方式

| 按键 | 动作 |
|------|------|
| `W` / `↑` | 向前移动（物理驱动） |
| `S` / `↓` | 向后移动 |
| `A` / `←` | 向左移动 |
| `D` / `→` | 向右移动 |
| `空格` | 跳跃（仅在地面时，Bullet 射线检测） |
| `E` | 在玩家前方生成物理方块 |
| `V` | 切换视角：第三人称 → 第一人称 → 轨道相机 |
| `鼠标左键` | 拾取/选中场景中的方块（高亮显示）/ 拾取经验方块 |
| `Delete` / `X` | 删除选中的方块 |
| `鼠标右键拖拽` | 旋转 3D 视角（所有相机模式） |
| `滚轮` | 缩放相机距离（轨道 / 第三人称模式） |
| `F1` | 打开设置面板 → 调试 Tab |
| `F2` | 打开设置面板 → 物理参数 Tab |
| `ESC` | 退出 |

---

## 功能特性

### 🎯 Bullet 物理引擎 (`src/physics.py`)

- **物理世界**：`BulletWorld`，重力 -9.81 m/s²
- **静态地面**：`BulletPlaneShape` 无限平面
- **玩家刚体**：`BulletSphereShape` 球形碰撞体，锁定旋转防止翻滚
- **动态方块**：E 键生成 `BulletBoxShape` 方块，受重力影响，可被推动
- **静态障碍物**：4 个预置棕色方块
- **调试渲染**：设置面板调试 Tab 控制线框/包围盒/法线显示

### 🦘 跳跃 + 地面检测 (`src/player.py`)

- **空格键跳跃**：仅在地面时可跳跃（防止空中连跳）
- **Bullet 射线检测**：`rayTestClosest` 向下发射射线判断是否着地
- **跳跃力度可调**：设置面板滑块实时调节（1.0 ~ 20.0）
- **HUD 状态指示**：右上角显示「地面: ✓」或「空中: ↑」

### 🔊 音效系统 (`src/audio.py`)

- **跳跃音效**：起跳时播放
- **生成音效**：E 键生成方块时播放
- **拾取音效**：鼠标左键选中方块时播放
- **删除音效**：删除方块时播放
- **音量控制**：设置面板滑块实时调节（0 ~ 1.0）
- 使用 Panda3D `AudioManager` + OpenAL 驱动

### 🖱️ 鼠标拾取交互 (`src/picking.py`)

- **射线拾取**：鼠标左键点击，通过 `camLens.extrude()` + `rayTestClosest` 发射射线
- **选中高亮**：被选中的方块变为亮黄色
- **删除方块**：按 `Delete` 或 `X` 键删除选中方块（从物理世界和场景图同时移除）
- **点击空白取消**：点击非方块区域自动取消选中

### 🎥 多模式相机 (`src/camera.py`)

**V 键循环切换**三种视角模式：

| 模式 | 说明 |
|------|------|
| 第三人称（默认） | 相机在玩家身后上方，跟随玩家，鼠标右键旋转，滚轮调整距离（3~30） |
| 第一人称 | 相机在玩家头部位置，鼠标右键控制视线方向 |
| 轨道相机 | 自由旋转 + 滚轮缩放（5~80），俯仰角 -80°~10° |

- 所有模式均支持鼠标右键拖拽旋转视角
- HUD 右上角实时显示当前视角模式

### 🔧 设置面板 (`src/settings_panel.py`)

右上角「⚙ 设置」按钮展开/收起，包含 2 个 Tab：

**🔍 调试 Tab**（F1 快捷键）

| 选项 | 说明 |
|------|------|
| 碰撞体线框 | 显示/隐藏 Bullet 碰撞体线框 |
| 包围盒显示 | 显示/隐藏 AABB 包围盒 |
| 法线显示 | 显示/隐藏碰撞面法线 |

**⚡ 物理参数 Tab**（F2 快捷键）

| 参数 | 范围 | 默认值 |
|------|------|--------|
| 重力 | -30 ~ 0 | -9.81 |
| 玩家质量 | 0.5 ~ 50 | 5.0 |
| 玩家摩擦力 | 0 ~ 5 | 1.0 |
| 玩家弹性 | 0 ~ 2 | 0.0 |
| 跳跃力度 | 1 ~ 20 | 6.0 |
| 方块质量 | 0.1 ~ 20 | 1.0 |
| 方块摩擦力 | 0 ~ 5 | 0.8 |
| 方块弹性 | 0 ~ 2 | 0.4 |
| 地面摩擦力 | 0 ~ 5 | 1.0 |
| 地面弹性 | 0 ~ 2 | 0.3 |
| 音效音量 | 0 ~ 1 | 0.7 |

- 拖动滑块立即生效
- 方块参数变更同步应用到所有已生成方块
- 「重置默认值」按钮一键恢复

### 🀄 中文字体支持 (`src/hud.py`)

- 自动加载 macOS 系统中文字体（华文黑体 / 冬青黑体 / 宋体）
- HUD 提示文字和设置面板均支持中文显示

### 💡 光照系统 (`src/scene.py`)

- 环境光（AmbientLight）：全局柔和照明
- 方向光（DirectionalLight）：模拟太阳光

### 💎 经验值系统 (`src/collectibles.py` + `src/player.py`)

- **自动生成**：每 3 秒在场景随机位置生成一个经验方块（最多 15 个）
- **随机经验值**：每个方块携带 1~10 点随机经验值
- **颜色编码**：低经验偏绿色，高经验偏金色，一目了然
- **自动拾取**：玩家靠近方块（距离 < 2.5）自动拾取
- **点击拾取**：鼠标左键点击经验方块也可拾取
- **浮动提示**：拾取时屏幕中央显示「+N EXP ✨」
- **经验累计**：玩家经验值持续累加，HUD 实时显示

### 📊 HUD 信息 (`src/hud.py`)

- 左上角：操作提示（中文）
- 右上角：实时 FPS + 方块计数 + 地面/空中状态 + 经验值 + 宝石数量

---

## 模块架构说明

```
main.py (MyGame : ShowBase)  ~170 行
│
├── 初始化子系统
│   ├── PhysicsManager       src/physics.py
│   ├── PlayerController     src/player.py
│   ├── OrbitCamera          src/camera.py
│   ├── AudioManager         src/audio.py
│   ├── PickingManager       src/picking.py
│   ├── CollectibleManager   src/collectibles.py
│   ├── SceneBuilder         src/scene.py
│   ├── HUD                  src/hud.py
│   └── SettingsPanel        src/settings_panel.py
│
├── _setup_input()           键盘 + 鼠标事件 → 委托给子系统
│
└── _update() [Task]         主循环
    ├── player.update()      物理移动
    ├── physics.step()       Bullet 步进
    ├── collectibles.update() 经验方块生成 + 自动拾取
    ├── orbit_cam.update()   相机跟随
    └── hud.update()         HUD 刷新
```

### 模块职责

| 模块 | 类 | 职责 |
|------|-----|------|
| `constants.py` | — | 全局常量、默认参数、字体路径、经验方块参数 |
| `physics.py` | `PhysicsManager` | BulletWorld、地面、方块生成/删除、调试渲染 |
| `player.py` | `PlayerController` | 玩家物理体、WASD 移动、跳跃、地面检测、经验值 |
| `camera.py` | `OrbitCamera` | 鼠标右键旋转、滚轮缩放、球坐标计算 |
| `audio.py` | `AudioManager` | 音效加载、播放、音量控制 |
| `picking.py` | `PickingManager` | 射线拾取、选中高亮、删除方块、经验方块点击拾取 |
| `collectibles.py` | `CollectibleManager` | 经验方块随机生成、自动拾取、经验值管理 |
| `scene.py` | `SceneBuilder` | 地面模型、静态障碍物、环境光 + 方向光 |
| `hud.py` | `HUD` | 中文字体加载、FPS/方块/地面状态/经验值显示 |
| `settings_panel.py` | `SettingsPanel` | 设置按钮、Tab 切换、调试开关、物理滑块 |

---

## 配置文件 config.prc

| 配置项 | 值 | 说明 |
|--------|-----|------|
| `win-size` | 1280 720 | 窗口分辨率 |
| `clock-frame-rate` | 60 | 帧率上限 |
| `multisamples` | 4 | 抗锯齿 |
| `audio-library-name` | p3openal_audio | 音频驱动 |
| `notify-level` | warning | 日志等级 |
| `framebuffer-srgb` | 1 | sRGB 颜色校正 |
| `model-path` | assets/models | 模型搜索路径 |

---

## 常用 Panda3D API 速查

### Bullet 物理

```python
from panda3d.bullet import (
    BulletWorld, BulletRigidBodyNode,
    BulletBoxShape, BulletSphereShape, BulletPlaneShape,
)

# 创建物理世界
world = BulletWorld()
world.setGravity(Vec3(0, 0, -9.81))

# 创建刚体
shape = BulletBoxShape(Vec3(0.5, 0.5, 0.5))
body = BulletRigidBodyNode("box")
body.setMass(1.0)          # 0 = 静态
body.addShape(shape)
body.setFriction(0.8)
body.setRestitution(0.4)   # 弹性
np = render.attachNewNode(body)
world.attachRigidBody(body)

# 每帧步进
world.doPhysics(dt, 10, 1.0/180.0)

# 控制速度
body.setActive(True)       # 唤醒休眠刚体
body.setLinearVelocity(Vec3(vx, vy, vz))
```

### 射线检测（地面 / 拾取）

```python
# 地面检测 — 向下发射射线
from_pos = player_np.getPos() + Vec3(0, 0, 0.1)
to_pos   = from_pos + Vec3(0, 0, -1.5)
result   = world.rayTestClosest(from_pos, to_pos)
on_ground = result.hasHit()

# 鼠标拾取 — 屏幕坐标 → 3D 射线
near, far = Point3(), Point3()
camLens.extrude(mouse_pos, near, far)
from_pos = render.getRelativePoint(camera, near)
to_pos   = render.getRelativePoint(camera, far)
result   = world.rayTestClosest(from_pos, to_pos)
if result.hasHit():
    hit_node = result.getNode()
```

### 音效

```python
sfx = loader.loadSfx("path/to/sound.wav")
sfx.setVolume(0.7)
sfx.play()
```

---

## 参考示例（panda3d-master/samples/）

| 目录 | 演示内容 |
|------|---------|
| `solar-system/` | 逐步教程：窗口→模型→动画→交互（6步） |
| `roaming-ralph/` | 第三人称角色在不平地形行走 + 碰撞 |
| `bullet-physics/` | Bullet 物理引擎集成 |
| `shadows/` | 阴影渲染 |
| `bump-mapping/` | 法线贴图 |
| `glow-filter/` | 后期处理滤镜 |
| `networking/` | 多人网络通信 |

---

## 常见问题

### macOS 打开时提示"无法验证开发者"

```bash
xattr -d com.apple.quarantine /Applications/Panda3D/*.pkg
```

### 找不到模型文件

在 `config.prc` 中添加：
```
model-path assets/models
```

### 音频无声

确认 `config.prc` 中：
```
audio-library-name p3openal_audio
```

### Bullet 刚体不响应速度设置

刚体休眠后 `setLinearVelocity()` 无效，需先调用：
```python
body.setActive(True)
```

### 中文显示为方块

确保系统字体路径正确，`src/hud.py` 中 `load_cjk_font()` 会自动尝试多个系统字体。

### 鼠标拾取无反应

确认已禁用默认相机控制（`disableMouse()`），且 `camLens.extrude()` 使用的是归一化鼠标坐标（-1 ~ 1）。

---

## 版本历史 (Changelog)

### v0.5.0 — 2026-05-30

**新增功能**

- 💎 **经验值系统**：熊猫角色新增经验值属性，拾取方块可累积经验
- 🎁 **可拾取经验方块**：场景中每 3 秒随机生成经验方块（最多 15 个）
- 🎲 **随机经验值**：每个方块携带 1~10 点随机经验值，颜色编码（绿→金）
- 🧲 **自动拾取**：玩家靠近方块（距离 < 2.5）自动拾取获得经验
- 🖱️ **点击拾取**：鼠标左键点击经验方块也可拾取
- ✨ **浮动提示**：拾取时屏幕中央显示「+N EXP ✨」（1.5 秒后消失）
- 🎥 **多模式相机**：V 键循环切换第三人称 / 第一人称 / 轨道相机
- 📊 HUD 新增经验值 + 宝石数量 + 视角模式显示
- 📁 新增 `src/collectibles.py` 模块

### v0.4.0 — 2026-05-30

**重构**

- 🏗️ **模块化重构**：1061 行单文件拆分为 9 个子模块 + 精简入口
- 📁 新增 `src/` 包：constants / physics / player / camera / audio / picking / scene / hud / settings_panel
- 📦 main.py 从 1061 行精简至 ~150 行（纯组合 + 事件绑定 + 主循环）
- 🔧 设置面板合并 F1 调试 + F2 物理参数为 Tab 切换界面
- ⚙ 右上角「设置」按钮展开/收起面板
- 📋 调试 Tab 新增包围盒、法线显示开关

### v0.3.0 — 2026-05-30

**新增功能**

- 🦘 **跳跃系统**：空格键跳跃，Bullet `rayTestClosest` 地面检测，防止空中连跳
- 🔊 **音效系统**：跳跃/生成/拾取/删除 4 种音效，UI 面板音量滑块
- 🖱️ **鼠标拾取交互**：左键射线拾取方块，高亮选中，Delete/X 删除
- 📊 HUD 新增地面/空中状态指示
- 🔧 物理面板新增跳跃力度、音效音量滑块（9 → 11 个）

**变更**

- 空格键从「生成方块」改为「跳跃」，E 键接管生成方块

### v0.2.0 — 2026-05-29

**新增功能**

- 🎯 **Bullet 物理引擎**：BulletWorld + 刚体 + 碰撞检测
- 🔧 **物理参数面板**：右侧 UI 面板，9 个滑块实时调节重力/质量/摩擦力/弹性
- 🎥 **轨道相机**：鼠标右键拖拽旋转 + 滚轮缩放
- 🀄 **中文字体支持**：自动加载 macOS 系统中文字体
- 💡 **光照系统**：环境光 + 方向光
- 📊 **HUD**：FPS + 方块计数 + 操作提示

### v0.1.0 — 2026-05-28

**初始版本**

- 基础 Panda3D 窗口 + 场景加载
- WASD / 方向键移动角色
- panda-model Actor 动画
- environment 地面模型
- config.prc 运行时配置

---

## 参考文档

- [Panda3D 官方文档](https://docs.panda3d.org/1.11/python/)
- [Panda3D Bullet 物理](https://docs.panda3d.org/1.11/python/programming/physics/bullet/index)
- [DirectGUI 参考](https://docs.panda3d.org/1.11/python/programming/gui/directgui/index)
- [API 参考](https://docs.panda3d.org/1.11/python/reference/)
- [社区论坛](https://discourse.panda3d.org/)
