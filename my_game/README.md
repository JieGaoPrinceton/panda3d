# 🎮 My Panda3D Game — Mac 开发模板

> **当前版本：v0.7.0** · 2026-05-30

基于 **Panda3D 1.11.0 + Python 3.13** 的 macOS 游戏开发起点模板。

集成 **Bullet 物理引擎**、**阴影渲染**、**粒子特效**、**雾效**、**天空盒**、**Interval 动画**、**后处理滤镜**、**日夜循环**、**NPC/AI 巡逻**、**NPC 对话框**、**碰撞触发区域**、**存档系统**、**小地图**、**游戏状态机 FSM**、**经验值系统**、**ESC 退出确认**。

---

## 环境要求

| 工具 | 版本 | 安装方式 |
|------|------|---------|
| macOS | 12 Monterey+ | — |
| Python | 3.13 | [python.org](https://www.python.org/) |
| Panda3D SDK | 1.11.0 | `Panda3D-1.11.0-py3.13.dmg` 或 `pip install panda3d` |

---

## 项目目录结构

```
my_game/
├── main.py                  # 游戏入口（组合各子系统）
├── config.prc               # Panda3D 运行时配置
├── ROADMAP.md               # 功能路线图 & 引擎对比分析
├── README.md                # 本文档
├── saves/                   # 存档目录（自动创建）
├── src/                     # 子模块包
│   ├── __init__.py
│   ├── constants.py         # 全局常量 & 默认参数
│   ├── physics.py           # Bullet 物理引擎管理
│   ├── player.py            # 玩家控制（移动 + 跳跃 + 经验值）
│   ├── camera.py            # 轨道相机（三种模式）
│   ├── audio.py             # 音效系统
│   ├── picking.py           # 鼠标拾取交互
│   ├── collectibles.py      # 可拾取经验方块
│   ├── scene.py             # 场景构建（地面 + 障碍物 + 光照）
│   ├── hud.py               # HUD 信息 + 中文字体
│   ├── settings_panel.py    # 设置面板（调试/物理/快捷键 三Tab）
│   ├── shadows.py           # ✨ 阴影渲染系统
│   ├── particles_fx.py      # ✨ 粒子特效系统
│   ├── fog.py               # ✨ 雾效系统
│   ├── skybox.py            # ✨ 程序化天空盒
│   ├── animations.py        # ✨ Interval 动画系统
│   ├── post_processing.py   # ✨ 后处理滤镜（Bloom/AO/模糊）
│   ├── day_night.py         # ✨ 日夜循环系统
│   ├── collision.py         # ✨ Panda3D 原生碰撞系统
│   ├── npc.py               # ✨ NPC / AI 巡逻系统
│   ├── dialogue.py          # ✨ NPC 对话框
│   ├── exit_dialog.py       # ✨ ESC 退出确认对话框
│   ├── save_load.py         # ✨ 存档 / 读档系统
│   ├── minimap.py           # ✨ 小地图系统（圆形标记）
│   └── game_fsm.py          # ✨ 游戏状态机 FSM
└── assets/
    ├── models/              # .egg.pz 3D 模型 + maps/ 贴图
    └── sounds/              # .wav 音效
```

---

## 快速启动

```bash
cd /Users/mac/code/panda3d-master/my_game
python3 main.py
```

---

## 操作方式

### 基础操作

| 按键 | 动作 |
|------|------|
| `W` / `↑` | 向前移动 |
| `S` / `↓` | 向后移动 |
| `A` / `←` | 向左移动 |
| `D` / `→` | 向右移动 |
| `空格` | 跳跃（仅在地面时） |
| `E` | 生成物理方块（带弹跳动画） |
| `V` | 切换视角：第三人称 → 第一人称 → 轨道相机 |
| `鼠标左键` | 拾取/选中方块 / 拾取经验方块 |
| `Delete` / `X` | 删除选中方块 |
| `鼠标右键拖拽` | 旋转 3D 视角 |
| `滚轮` | 缩放相机距离 |
| `ESC` | 退出确认对话框（存档/退出/继续） |

### 新增快捷键 (v0.6.0)

| 按键 | 动作 |
|------|------|
| `P` | 暂停 / 恢复游戏 |
| `F1` | 设置面板 → 调试 Tab |
| `F2` | 设置面板 → 物理参数 Tab |
| `F3` | 切换阴影渲染 |
| `F4` | 切换雾效 |
| `F5` | 快速保存 |
| `F6` | 切换天空盒 |
| `F7` | 切换 Bloom 泛光 |
| `F8` | 切换日夜循环 |
| `F9` | 快速加载 |
| `M` | 切换小地图 |
| `N` | 切换 NPC 显示 |
| `T` | 加速时间（1x → 2x → 5x → 10x 循环） |

---

## 功能特性

### 🎯 Bullet 物理引擎 (`src/physics.py`)

- **物理世界**：`BulletWorld`，重力 -9.81 m/s²
- **静态地面**：`BulletPlaneShape` 无限平面
- **玩家刚体**：`BulletSphereShape` 球形碰撞体
- **动态方块**：E 键生成 `BulletBoxShape` 方块
- **调试渲染**：设置面板调试 Tab 控制线框/包围盒/法线显示

### 🌑 阴影渲染 (`src/shadows.py`) ✨ NEW

- **实时阴影**：`DirectionalLight.setShadowCaster()` 阴影贴图
- **分辨率可调**：512 / 1024 / 2048 / 4096
- **F3 快捷键**：一键开关阴影
- **自动 Shader**：`render.setShaderAuto()` 启用

### 🎆 粒子特效 (`src/particles_fx.py`) ✨ NEW

- **跳跃尘土**：落地时脚下扬尘效果
- **经验星光**：拾取经验方块时金色星光爆发
- **碰撞火花**：方块碰撞时橙色火花
- **自动清理**：粒子效果定时自动销毁

### 🌫️ 雾效系统 (`src/fog.py`) ✨ NEW

- **线性雾**：可调起始/结束距离
- **指数雾**：可调密度
- **雾颜色**：可自定义（与日夜循环联动）
- **F4 快捷键**：一键开关

### 🌤️ 天空盒 (`src/skybox.py`) ✨ NEW

- **程序化天空球**：顶点色渐变（天顶蓝 → 地平线白 → 底部灰）
- **跟随相机**：`CompassEffect` 保持天空始终包围
- **颜色可调**：与日夜循环联动
- **F6 快捷键**：一键开关

### 🎬 Interval 动画 (`src/animations.py`) ✨ NEW

- **方块弹跳**：生成时 0→1.3→0.9→1.0 缩放动画
- **高亮脉冲**：选中物体颜色闪烁
- **相机过渡**：模式切换平滑插值
- **旋转/呼吸**：物体持续旋转、缩放呼吸效果
- **震动效果**：受击/碰撞反馈

### ✨ 后处理滤镜 (`src/post_processing.py`) ✨ NEW

- **Bloom 泛光**：`CommonFilters.setBloom()` 发光效果
- **环境光遮蔽 AO**：增强立体感
- **模糊/锐化**：`setBlurSharpen()` 可调
- **颜色反转**：特殊效果
- **HDR 色调映射**：高动态范围
- **F7 快捷键**：切换 Bloom

### 🌅 日夜循环 (`src/day_night.py`) ✨ NEW

- **自动日夜交替**：120 秒一天（可调）
- **太阳方向旋转**：模拟真实日照角度
- **光照颜色渐变**：午夜深蓝 → 日出橙红 → 正午白色 → 日落橙色
- **天空盒联动**：天空颜色随时间变化
- **雾效联动**：雾颜色随时间变化
- **F8 快捷键**：开关日夜循环
- **T 键**：加速时间（1x/2x/5x/10x）

### 🎯 碰撞触发区域 (`src/collision.py`) ✨ NEW

- **Panda3D 原生碰撞**：`CollisionTraverser` + `CollisionHandlerEvent`
- **球形/方形触发区域**：进入/离开事件回调
- **演示区域**：加速区域 + 危险区域
- **碰撞可视化**：调试显示碰撞体

### 🤖 NPC / AI (`src/npc.py`) ✨ NEW

- **巡逻行为**：沿路径点自动巡逻
- **追逐行为**：检测到玩家后追逐
- **返回行为**：丢失玩家后返回巡逻路径
- **视野检测**：可调检测/丢失距离
- **N 键**：切换 NPC 显示

### 💾 存档系统 (`src/save_load.py`) ✨ NEW

- **JSON 格式**：人类可读的存档文件
- **F5 快速保存**：保存玩家位置、经验值、方块状态
- **F9 快速加载**：恢复游戏状态
- **日夜循环状态**：保存/恢复时间

### 🗺️ 小地图 (`src/minimap.py`) ✨ NEW

- **俯视相机**：独立正交相机
- **右下角显示**：`DisplayRegion` 独立渲染区域
- **玩家标记**：红色圆形标记（程序化几何体 triangle fan）
- **跟随玩家**：相机自动跟随
- **M 键**：切换显示

### 🎮 游戏状态机 (`src/game_fsm.py`) ✨ NEW

- **FSM 架构**：`direct.fsm.FSM` 状态管理
- **四种状态**：Menu → Playing → Paused → GameOver
- **暂停菜单**：P 键暂停，显示继续/主菜单/退出
- **主菜单**：开始游戏 / 退出
- **游戏结束**：重新开始 / 退出

### 🦘 跳跃 + 地面检测 (`src/player.py`)

- **空格键跳跃**：仅在地面时可跳跃
- **Bullet 射线检测**：`rayTestClosest` 地面判断
- **跳跃力度可调**：设置面板滑块

### 🔊 音效系统 (`src/audio.py`)

- **4 种音效**：跳跃/生成/拾取/删除
- **音量控制**：设置面板滑块

### 🖱️ 鼠标拾取 (`src/picking.py`)

- **射线拾取**：`camLens.extrude()` + `rayTestClosest`
- **选中高亮**：亮黄色
- **删除方块**：Delete/X 键

### 🎥 多模式相机 (`src/camera.py`)

| 模式 | 说明 |
|------|------|
| 第三人称 | 跟随玩家，鼠标右键旋转 |
| 第一人称 | 头部视角，鼠标控制视线 |
| 轨道相机 | 自由旋转 + 缩放 |

### 💎 经验值系统 (`src/collectibles.py`)

- **自动生成**：每 3 秒随机生成经验方块
- **颜色编码**：低经验绿色 → 高经验金色
- **自动/点击拾取**：靠近或点击均可

### 🔧 设置面板 (`src/settings_panel.py`)

- **调试 Tab**：碰撞体线框/包围盒/法线
- **物理参数 Tab**：11 个滑块实时调节
- **快捷键 Tab**：全部 25 个快捷键一览

### 💬 NPC 对话框 (`src/dialogue.py`) ✨ NEW

- **触发条件**：NPC 进入追逐状态时自动弹出
- **随机中文**：每次生成 20 个随机中文字符
- **自动隐藏**：4 秒后自动消失
- **底部显示**：屏幕最下方对话框

### 🚪 ESC 退出确认 (`src/exit_dialog.py`) ✨ NEW

- **半透明遮罩**：全屏暗色遮罩
- **三个选项**：💾 存档并退出 / 🚪 直接退出 / ▶ 继续游戏
- **自动暂停**：弹出时暂停游戏，关闭时恢复
- **再按 ESC**：等同于"继续游戏"

---

## 模块架构说明

```
main.py (MyGame : ShowBase)
│
├── 核心系统
│   ├── PhysicsManager       src/physics.py
│   ├── PlayerController     src/player.py      (WASD 跟随相机朝向)
│   ├── OrbitCamera          src/camera.py
│   ├── AudioManager         src/audio.py
│   ├── PickingManager       src/picking.py
│   ├── CollectibleManager   src/collectibles.py
│   ├── SceneBuilder         src/scene.py
│   ├── HUD                  src/hud.py
│   └── SettingsPanel        src/settings_panel.py  (3 Tab: 调试/物理/快捷键)
│
├── 渲染增强 (v0.6.0+)
│   ├── ShadowManager        src/shadows.py
│   ├── FogManager           src/fog.py
│   ├── SkyBox               src/skybox.py
│   ├── PostProcessing       src/post_processing.py
│   └── AnimationManager     src/animations.py
│
├── 游戏系统 (v0.6.0+)
│   ├── DayNightCycle        src/day_night.py
│   ├── CollisionManager     src/collision.py
│   ├── NPCManager           src/npc.py
│   ├── DialogueBox          src/dialogue.py     (v0.7.0)
│   ├── ExitDialog           src/exit_dialog.py  (v0.7.0)
│   ├── SaveLoadManager      src/save_load.py
│   ├── MiniMap              src/minimap.py
│   └── GameFSM              src/game_fsm.py
│
├── _setup_input()           键盘 + 鼠标事件
│
└── _update() [Task]         主循环
    ├── player.update()      物理移动 (相机朝向旋转)
    ├── physics.step()       Bullet 步进
    ├── collectibles.update() 经验方块
    ├── collision.update()   原生碰撞检测
    ├── npc_mgr.update()     NPC AI + 对话触发
    ├── dialogue.update()    对话框倒计时
    ├── day_night.update()   日夜循环
    ├── minimap.update()     小地图
    ├── orbit_cam.update()   相机跟随
    └── hud.update()         HUD 刷新
```

---

## Panda3D 引擎功能覆盖

> 详见 [ROADMAP.md](ROADMAP.md) 完整对比分析（16 大类 95 项功能）。
> 统计：✅ 已实现 **42 项** · ❌ 未实现 **35 项** · 覆盖率 **55%**

| 子系统 | 已实现 | 未实现 | 覆盖率 | 代表模块 |
|--------|-------|--------|--------|---------|
| 场景图 & 渲染 | 8/13 | 5 | 62% | `scene.py`, `skybox.py`, `minimap.py` |
| 光照 & 阴影 | 3/8 | 5 | 38% | `scene.py`, `shadows.py` |
| 动画系统 | 2/5 | 3 | 40% | `player.py`, `animations.py` |
| 物理引擎 | 4/10 | 6 | 40% | `physics.py`, `player.py` |
| 碰撞检测 | 3/5 | 2 | 60% | `collision.py` |
| GUI 系统 | 5/9 | 4 | 56% | `settings_panel.py`, `hud.py`, `exit_dialog.py` |
| 音频系统 | 2/5 | 3 | 40% | `audio.py` |
| 输入系统 | 2/5 | 3 | 40% | `main.py`, `camera.py` |
| 粒子系统 | 3/4 | 1 | 75% | `particles_fx.py` |
| 后处理滤镜 | 5/7 | 2 | 71% | `post_processing.py` |
| 地形 & 环境 | 1/4 | 3 | 25% | `skybox.py` |
| 任务 & 事件 | 3/3 | 0 | 100% | `main.py`, `game_fsm.py` |
| 文件 & 资源 | 4/6 | 2 | 67% | `main.py`, `scene.py` |
| 文本 & 字体 | 3/4 | 1 | 75% | `hud.py`, `dialogue.py` |
| 网络 & 分布式 | 0/3 | 3 | 0% | — |
| 窗口 & 显示 | 2/4 | 2 | 50% | `main.py` |

---

## 版本历史 (Changelog)

### v0.7.0 — 2026-05-30

**新增功能**

- 💬 **NPC 对话框**：遇到 NPC 时底部弹出对话框，随机生成 20 个中文字，4 秒自动消失
- 🚪 **ESC 退出确认**：按 ESC 弹出确认对话框（存档并退出 / 直接退出 / 继续游戏）
- ⌨ **快捷键标签页**：设置面板新增第三个 Tab，列出全部 25 个快捷键
- 🔴 **小地图圆形标记**：玩家位置改为红色圆形（程序化几何体 triangle fan）

**修复 & 改进**

- 🔧 **WASD 方向修复**：基于相机前方/右方向量正确推导旋转矩阵，前后左右方向准确
- 🔧 **模型朝向修复**：熊猫模型面朝移动方向（+180° 偏移适配模型默认朝向）
- 🔧 **相机跟随**：切换视角模式后 WASD 自动跟随新坐标系
- 📝 **代码重构**：main.py / player.py / camera.py / physics.py / scene.py / constants.py 增加详细注释

### v0.6.0 — 2026-05-30

**新增功能（12 个新模块）**

- 🌑 **阴影渲染**：`DirectionalLight` 实时阴影，F3 开关，分辨率可调
- 🎆 **粒子特效**：跳跃尘土 / 经验星光 / 碰撞火花，自动清理
- 🌫️ **雾效系统**：线性雾 / 指数雾，颜色可调，F4 开关
- 🌤️ **天空盒**：程序化渐变天空球，F6 开关
- 🎬 **Interval 动画**：方块弹跳 / 高亮脉冲 / 震动 / 呼吸效果
- ✨ **后处理滤镜**：Bloom / AO / 模糊 / HDR，F7 切换 Bloom
- 🌅 **日夜循环**：120 秒一天，光照/天空/雾联动，F8 开关，T 加速
- 🎯 **碰撞触发区域**：Panda3D 原生碰撞，进入/离开事件
- 🤖 **NPC / AI**：巡逻 → 追逐 → 返回 状态机，N 键开关
- 💾 **存档系统**：JSON 格式，F5 保存 / F9 加载
- 🗺️ **小地图**：俯视正交相机，右下角 DisplayRegion，M 键开关
- 🎮 **游戏状态机**：FSM 管理 Menu/Playing/Paused/GameOver，P 键暂停

**新增快捷键**

- `P` 暂停 · `F3` 阴影 · `F4` 雾效 · `F5` 保存 · `F6` 天空盒
- `F7` Bloom · `F8` 日夜 · `F9` 加载 · `M` 小地图 · `N` NPC · `T` 加速时间

### v0.5.0 — 2026-05-30

- 💎 经验值系统 + 可拾取经验方块
- 🎥 多模式相机（V 键切换）
- 📁 新增 `src/collectibles.py`

### v0.4.0 — 2026-05-30

- 🏗️ 模块化重构：9 个子模块 + 精简入口

### v0.3.0 — 2026-05-30

- 🦘 跳跃系统 + 🔊 音效系统 + 🖱️ 鼠标拾取

### v0.2.0 — 2026-05-29

- 🎯 Bullet 物理 + 🔧 参数面板 + 🎥 轨道相机 + 🀄 中文字体

### v0.1.0 — 2026-05-28

- 基础窗口 + WASD 移动 + Actor 动画

---

## 参考文档

- [Panda3D 官方文档](https://docs.panda3d.org/1.11/python/)
- [Panda3D Bullet 物理](https://docs.panda3d.org/1.11/python/programming/physics/bullet/index)
- [CommonFilters 后处理](https://docs.panda3d.org/1.11/python/programming/render-effects/common-image-filters)
- [FSM 状态机](https://docs.panda3d.org/1.11/python/programming/tasks-and-events/finite-state-machines)
- [粒子系统](https://docs.panda3d.org/1.11/python/programming/particle-effects/index)
- [碰撞检测](https://docs.panda3d.org/1.11/python/programming/collision-detection/index)
- [DirectGUI 参考](https://docs.panda3d.org/1.11/python/programming/gui/directgui/index)
- [API 参考](https://docs.panda3d.org/1.11/python/reference/)
