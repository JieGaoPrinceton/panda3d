# 🗺️ My Panda3D Game — 功能 Roadmap

> **基于 Panda3D 引擎能力 vs my_game 现有实现的差距分析**
>
> 最后更新：2026-05-30 · **v0.7.0**

---

## 📊 Panda3D 引擎功能全表 vs my_game 实现状态

> 以下按引擎子系统分类，覆盖 Panda3D 1.11.0 的**全部核心功能模块**。
> 统计：✅ 已实现 25 项 · ❌ 未实现 35 项 · 覆盖率 **42%**

### 一、场景图 & 渲染管线 (`panda3d.core` · `panda/src/pgraph`)

| # | 引擎功能 | 引擎模块 / API | my_game 状态 | 实现模块 | 版本 |
|---|---------|---------------|-------------|---------|------|
| 1 | 场景图节点管理 | `NodePath`, `PandaNode`, `reparentTo()` | ✅ 已实现 | 全部模块 | v0.1.0 |
| 2 | 模型加载 (.egg/.bam/.gltf) | `loader.loadModel()` | ✅ 已实现 | `scene.py`, `player.py` | v0.1.0 |
| 3 | 纹理 & 贴图 | `TexturePool`, `setTexture()` | ✅ 已实现 | `scene.py` | v0.1.0 |
| 4 | 渲染属性 (RenderAttrib) | `TransparencyAttrib`, `ColorAttrib`, `CullFaceAttrib` | ✅ 部分 | `skybox.py`, `minimap.py` | v0.6.0 |
| 5 | Shader 自动生成 | `render.setShaderAuto()` | ✅ 已实现 | `shadows.py` | v0.6.0 |
| 6 | 自定义 GLSL Shader | `Shader.load()`, `Shader.make()` | ❌ 未实现 | — | — |
| 7 | 渲染到纹理 (RTT) | `makeTextureBuffer()`, `GraphicsOutput` | ❌ 未实现 | — | — |
| 8 | 多渲染通道 (Multi-pass) | `GraphicsEngine`, `DisplayRegion` | ✅ 部分 | `minimap.py` | v0.6.0 |
| 9 | 遮挡剔除 | `OccluderNode`, `occluder` | ❌ 未实现 | — | — |
| 10 | LOD 层次细节 | `LODNode`, `FadeLODNode` | ❌ 未实现 | — | — |
| 11 | 实例化渲染 | `instanceTo()`, `setInstanceCount()` | ❌ 未实现 | — | — |
| 12 | 雾效 | `Fog`, `setFog()` | ✅ 已实现 | `fog.py` | v0.6.0 |
| 13 | 程序化几何体 | `GeomVertexData`, `GeomTriangles`, `GeomNode` | ✅ 已实现 | `skybox.py`, `minimap.py` | v0.6.0 |

### 二、光照 & 阴影 (`panda3d.core` · `panda/src/pgraphnodes`)

| # | 引擎功能 | 引擎模块 / API | my_game 状态 | 实现模块 | 版本 |
|---|---------|---------------|-------------|---------|------|
| 14 | 环境光 | `AmbientLight` | ✅ 已实现 | `scene.py` | v0.2.0 |
| 15 | 平行光 (太阳光) | `DirectionalLight` | ✅ 已实现 | `scene.py` | v0.2.0 |
| 16 | 点光源 | `PointLight` | ❌ 未实现 | — | — |
| 17 | 聚光灯 | `Spotlight` | ❌ 未实现 | — | — |
| 18 | 阴影贴图 | `setShadowCaster()`, shadow buffer | ✅ 已实现 | `shadows.py` | v0.6.0 |
| 19 | 光照衰减 | `setAttenuation()` | ❌ 未实现 | — | — |
| 20 | 法线贴图 / Bump Mapping | `setNormalMap()`, tangent-space shader | ❌ 未实现 | — | — |
| 21 | 卡通渲染 (Toon Shader) | `LightRampAttrib`, ink outline | ❌ 未实现 | — | — |

### 三、动画系统 (`direct.actor` · `direct.interval` · `panda/src/chan`)

| # | 引擎功能 | 引擎模块 / API | my_game 状态 | 实现模块 | 版本 |
|---|---------|---------------|-------------|---------|------|
| 22 | Actor 骨骼动画 | `Actor`, `loop()`, `play()` | ✅ 已实现 | `player.py` | v0.1.0 |
| 23 | 动画混合 / 过渡 | `Actor.blend()`, `enableBlend()` | ❌ 未实现 | — | — |
| 24 | 关节暴露 / IK | `exposeJoint()`, `controlJoint()` | ❌ 未实现 | — | — |
| 25 | Interval 动画 | `LerpInterval`, `Sequence`, `Parallel`, `Func` | ✅ 已实现 | `animations.py` | v0.6.0 |
| 26 | 运动拖尾 | `MotionTrail` | ❌ 未实现 | — | — |

### 四、物理引擎 (`panda3d.bullet` · `panda3d.ode`)

| # | 引擎功能 | 引擎模块 / API | my_game 状态 | 实现模块 | 版本 |
|---|---------|---------------|-------------|---------|------|
| 27 | Bullet 刚体物理 | `BulletWorld`, `BulletRigidBodyNode` | ✅ 已实现 | `physics.py` | v0.2.0 |
| 28 | Bullet 碰撞形状 | `BulletBoxShape`, `BulletSphereShape`, `BulletPlaneShape` | ✅ 已实现 | `physics.py`, `player.py` | v0.2.0 |
| 29 | Bullet 射线检测 | `rayTestClosest()`, `rayTestAll()` | ✅ 已实现 | `picking.py`, `player.py` | v0.3.0 |
| 30 | Bullet 调试渲染 | `BulletDebugNode` | ✅ 已实现 | `physics.py` | v0.2.0 |
| 31 | Bullet 约束 (铰链/滑块) | `BulletHingeConstraint`, `BulletSliderConstraint` | ❌ 未实现 | — | — |
| 32 | Bullet 软体 | `BulletSoftBodyNode` | ❌ 未实现 | — | — |
| 33 | Bullet 车辆 | `BulletVehicle` | ❌ 未实现 | — | — |
| 34 | Bullet 角色控制器 | `BulletCharacterControllerNode` | ❌ 未实现 | — | — |
| 35 | ODE 物理引擎 | `panda3d.ode` | ❌ 未实现 | — | — |
| 36 | 内置物理 (简单) | `panda3d.physics`, `ForceNode` | ❌ 未实现 | — | — |

### 五、碰撞检测 (`panda3d.core` · `panda/src/collide`)

| # | 引擎功能 | 引擎模块 / API | my_game 状态 | 实现模块 | 版本 |
|---|---------|---------------|-------------|---------|------|
| 37 | 碰撞遍历器 | `CollisionTraverser` | ✅ 已实现 | `collision.py` | v0.6.0 |
| 38 | 碰撞事件处理 | `CollisionHandlerEvent` | ✅ 已实现 | `collision.py` | v0.6.0 |
| 39 | 碰撞推送处理 | `CollisionHandlerPusher` | ❌ 未实现 | — | — |
| 40 | 碰撞物理处理 | `CollisionHandlerFloor`, `CollisionHandlerGravity` | ❌ 未实现 | — | — |
| 41 | 碰撞形状 | `CollisionSphere`, `CollisionBox`, `CollisionRay` | ✅ 已实现 | `collision.py` | v0.6.0 |

### 六、GUI 系统 (`direct.gui` · `panda/src/pgui`)

| # | 引擎功能 | 引擎模块 / API | my_game 状态 | 实现模块 | 版本 |
|---|---------|---------------|-------------|---------|------|
| 42 | DirectButton | `DirectButton` | ✅ 已实现 | `settings_panel.py`, `game_fsm.py`, `exit_dialog.py` | v0.2.0 |
| 43 | DirectFrame | `DirectFrame` | ✅ 已实现 | `settings_panel.py`, `dialogue.py` | v0.2.0 |
| 44 | DirectLabel | `DirectLabel` | ✅ 已实现 | `settings_panel.py`, `hud.py` | v0.2.0 |
| 45 | DirectSlider | `DirectSlider` | ✅ 已实现 | `settings_panel.py` | v0.2.0 |
| 46 | DirectEntry (文本输入) | `DirectEntry` | ❌ 未实现 | — | — |
| 47 | DirectScrolledList | `DirectScrolledList` | ❌ 未实现 | — | — |
| 48 | DirectDialog | `DirectDialog`, `OkDialog`, `YesNoDialog` | ❌ 未实现 | — | — |
| 49 | OnscreenText | `OnscreenText` | ✅ 已实现 | `hud.py`, `dialogue.py` | v0.2.0 |
| 50 | OnscreenImage | `OnscreenImage` | ❌ 未实现 | — | — |

### 七、音频系统 (`panda3d.core` · `panda/src/audio`)

| # | 引擎功能 | 引擎模块 / API | my_game 状态 | 实现模块 | 版本 |
|---|---------|---------------|-------------|---------|------|
| 51 | 音效加载 & 播放 | `loader.loadSfx()`, `play()` | ✅ 已实现 | `audio.py` | v0.3.0 |
| 52 | 音量控制 | `setVolume()` | ✅ 已实现 | `audio.py`, `settings_panel.py` | v0.3.0 |
| 53 | 3D 空间音效 | `AudioSound3D`, `setPos()` | ❌ 未实现 | — | — |
| 54 | 背景音乐 | `loader.loadMusic()`, `setLoop()` | ❌ 未实现 | — | — |
| 55 | 视频/媒体播放 | `MovieTexture`, `MovieVideo` | ❌ 未实现 | — | — |

### 八、输入系统 (`panda3d.core` · `panda/src/device`)

| # | 引擎功能 | 引擎模块 / API | my_game 状态 | 实现模块 | 版本 |
|---|---------|---------------|-------------|---------|------|
| 56 | 键盘输入 | `accept()`, `KeyboardButton` | ✅ 已实现 | `main.py` | v0.1.0 |
| 57 | 鼠标输入 | `mouseWatcherNode`, `getMouse()` | ✅ 已实现 | `camera.py`, `picking.py` | v0.2.0 |
| 58 | 鼠标模式 (相对/绝对/隐藏) | `WindowProperties.setCursorHidden()`, `setMouseMode()` | ❌ 未实现 | — | — |
| 59 | 手柄 / Gamepad | `InputDevice`, `InputDeviceManager` | ❌ 未实现 | — | — |
| 60 | 触摸输入 | `TouchInfo` | ❌ 未实现 | — | — |

### 九、粒子系统 (`direct.particles` · `panda/src/particlesystem`)

| # | 引擎功能 | 引擎模块 / API | my_game 状态 | 实现模块 | 版本 |
|---|---------|---------------|-------------|---------|------|
| 61 | 粒子效果 | `ParticleEffect`, `Particles` | ✅ 已实现 | `particles_fx.py` | v0.6.0 |
| 62 | 粒子发射器 | `SphereSurfaceEmitter`, `PointEmitter`, `RingEmitter` | ✅ 已实现 | `particles_fx.py` | v0.6.0 |
| 63 | 粒子渲染器 | `PointParticleRenderer`, `SpriteParticleRenderer` | ✅ 部分 | `particles_fx.py` | v0.6.0 |
| 64 | 粒子力场 | `LinearVectorForce`, `LinearJitterForce` | ❌ 未实现 | — | — |

### 十、后处理 & 滤镜 (`direct.filter`)

| # | 引擎功能 | 引擎模块 / API | my_game 状态 | 实现模块 | 版本 |
|---|---------|---------------|-------------|---------|------|
| 65 | Bloom 泛光 | `CommonFilters.setBloom()` | ✅ 已实现 | `post_processing.py` | v0.6.0 |
| 66 | 环境光遮蔽 AO | `CommonFilters.setAmbientOcclusion()` | ✅ 已实现 | `post_processing.py` | v0.6.0 |
| 67 | 模糊 / 锐化 | `CommonFilters.setBlurSharpen()` | ✅ 已实现 | `post_processing.py` | v0.6.0 |
| 68 | HDR 色调映射 | `CommonFilters.setHighDynamicRange()` | ✅ 已实现 | `post_processing.py` | v0.6.0 |
| 69 | 颜色反转 | `CommonFilters.setInverted()` | ✅ 已实现 | `post_processing.py` | v0.6.0 |
| 70 | 扭曲效果 | `distortion` shader | ❌ 未实现 | — | — |
| 71 | 景深 (DOF) | 自定义 shader | ❌ 未实现 | — | — |

### 十一、地形 & 环境 (`panda3d.core`)

| # | 引擎功能 | 引擎模块 / API | my_game 状态 | 实现模块 | 版本 |
|---|---------|---------------|-------------|---------|------|
| 72 | Shader 地形 | `ShaderTerrainMesh` | ❌ 未实现 | — | — |
| 73 | 高度图地形 | `GeoMipTerrain` | ❌ 未实现 | — | — |
| 74 | 天空盒 / 天空球 | 程序化几何体 + `CompassEffect` | ✅ 已实现 | `skybox.py` | v0.6.0 |
| 75 | 水面效果 | Shader + RTT + 扭曲 | ❌ 未实现 | — | — |

### 十二、任务 & 事件 (`direct.task` · `direct.showbase`)

| # | 引擎功能 | 引擎模块 / API | my_game 状态 | 实现模块 | 版本 |
|---|---------|---------------|-------------|---------|------|
| 76 | 任务管理器 | `taskMgr.add()`, `doMethodLater()` | ✅ 已实现 | `main.py`, `particles_fx.py` | v0.1.0 |
| 77 | 事件系统 | `accept()`, `messenger.send()` | ✅ 已实现 | `main.py`, `collision.py` | v0.1.0 |
| 78 | FSM 状态机 | `direct.fsm.FSM` | ✅ 已实现 | `game_fsm.py` | v0.6.0 |

### 十三、文件 & 资源 (`panda3d.core`)

| # | 引擎功能 | 引擎模块 / API | my_game 状态 | 实现模块 | 版本 |
|---|---------|---------------|-------------|---------|------|
| 79 | 模型格式 (.egg) | `EggData`, `loadModel()` | ✅ 已实现 | `scene.py`, `player.py` | v0.1.0 |
| 80 | 模型格式 (.bam) | `BamFile`, `writeBamFile()` | ❌ 未使用 | — | — |
| 81 | 模型格式 (.gltf/.glb) | Assimp loader | ❌ 未使用 | — | — |
| 82 | 压缩模型 (.pz) | `loadModel("*.egg.pz")` | ✅ 已实现 | `scene.py`, `player.py` | v0.1.0 |
| 83 | 配置文件 | `loadPrcFileData()`, `config.prc` | ✅ 已实现 | `main.py`, `config.prc` | v0.1.0 |
| 84 | 虚拟文件系统 | `VirtualFileSystem`, `mount()` | ❌ 未实现 | — | — |

### 十四、文本 & 字体 (`panda3d.core` · `panda/src/text`)

| # | 引擎功能 | 引擎模块 / API | my_game 状态 | 实现模块 | 版本 |
|---|---------|---------------|-------------|---------|------|
| 85 | 动态文本字体 | `DynamicTextFont`, `loader.loadFont()` | ✅ 已实现 | `hud.py` | v0.2.0 |
| 86 | 静态文本字体 | `StaticTextFont` | ❌ 未使用 | — | — |
| 87 | 文本节点 | `TextNode`, `OnscreenText` | ✅ 已实现 | `hud.py`, `dialogue.py` | v0.2.0 |
| 88 | CJK 中文支持 | `DynamicTextFont` + 系统字体 | ✅ 已实现 | `hud.py` | v0.2.0 |

### 十五、网络 & 分布式 (`direct.distributed` · `panda/src/net`)

| # | 引擎功能 | 引擎模块 / API | my_game 状态 | 实现模块 | 版本 |
|---|---------|---------------|-------------|---------|------|
| 89 | 分布式对象 | `DistributedObject`, `DistributedNode` | ❌ 未实现 | — | — |
| 90 | 客户端/服务器 | `ClientRepository`, `ServerRepository` | ❌ 未实现 | — | — |
| 91 | 原生网络 | `panda3d.nativenet`, `Connection` | ❌ 未实现 | — | — |

### 十六、窗口 & 显示 (`panda3d.core` · `panda/src/display`)

| # | 引擎功能 | 引擎模块 / API | my_game 状态 | 实现模块 | 版本 |
|---|---------|---------------|-------------|---------|------|
| 92 | 窗口属性 | `WindowProperties`, `setTitle()`, `setSize()` | ✅ 已实现 | `main.py` | v0.1.0 |
| 93 | 全屏模式 | `WindowProperties.setFullscreen()` | ❌ 未实现 | — | — |
| 94 | 多窗口 | `openWindow()` | ❌ 未实现 | — | — |
| 95 | 帧率控制 | `globalClock`, `setFrameRate()` | ✅ 已实现 | `hud.py` | v0.2.0

---

## 🚀 实施路线图（分 Phase 逐步实现）

### ✅ Phase 1 — 阴影系统 `src/shadows.py` ⭐⭐ **已完成**
> **引擎能力**：`DirectionalLight.setShadowCaster(True, 2048, 2048)`

- ✅ 新增 `src/shadows.py` — `ShadowManager` 类
- ✅ 修改 `src/scene.py` — 暴露 `sun_np` 供阴影系统使用
- ✅ F3 快捷键切换阴影开关
- ✅ 阴影贴图分辨率可调（512/1024/2048/4096）
- ✅ `render.setShaderAuto()` 自动 Shader

### ✅ Phase 2 — 粒子特效 `src/particles_fx.py` ⭐⭐⭐ **已完成**
> **引擎能力**：`direct.particles.ParticleEffect`

- ✅ 跳跃落地尘土效果（`SphereSurfaceEmitter` + 重力）
- ✅ 经验拾取星光爆发（金色粒子）
- ✅ 方块碰撞火花效果（橙色粒子）
- ✅ 粒子自动清理（`doMethodLater` 定时销毁）

### ✅ Phase 3 — 雾效 `src/fog.py` ⭐ **已完成**
> **引擎能力**：`panda3d.core.Fog`

- ✅ 线性雾（可调起始/结束距离）
- ✅ 指数雾（可调密度）
- ✅ 雾颜色可自定义
- ✅ F4 快捷键切换
- ✅ 与日夜循环颜色联动

### ✅ Phase 4 — 天空盒 `src/skybox.py` ⭐⭐ **已完成**
> **引擎能力**：程序化几何体 + `CompassEffect`

- ✅ 程序化生成天空球（`GeomVertexData` + 顶点色）
- ✅ 渐变色天空（天顶蓝 → 地平线白 → 底部灰）
- ✅ `CompassEffect` 跟随相机
- ✅ F6 快捷键切换
- ✅ 颜色可调（与日夜循环联动）

### ✅ Phase 5 — Interval 动画 `src/animations.py` ⭐⭐ **已完成**
> **引擎能力**：`direct.interval` — Lerp / Sequence / Parallel / Func

- ✅ 方块生成弹跳动画（`LerpScaleInterval`）
- ✅ 经验拾取浮动文字动画（`LerpPosInterval` + `LerpColorScaleInterval`）
- ✅ 物体高亮脉冲动画
- ✅ 相机平滑过渡（`LerpPosInterval` + `LerpHprInterval`）
- ✅ 旋转/呼吸/震动效果

### ✅ Phase 6 — 原生碰撞系统 `src/collision.py` ⭐⭐ **已完成**
> **引擎能力**：`CollisionTraverser` + `CollisionHandlerEvent`

- ✅ 玩家碰撞球体（`CollisionSphere`）
- ✅ 球形/方形触发区域
- ✅ 进入/离开事件回调
- ✅ 演示触发区域（加速区域 + 危险区域）
- ✅ 碰撞可视化调试

### ✅ Phase 7 — 后处理滤镜 `src/post_processing.py` ⭐⭐ **已完成**
> **引擎能力**：`direct.filter.CommonFilters`

- ✅ Bloom 泛光（`setBloom()`）
- ✅ 环境光遮蔽 AO（`setAmbientOcclusion()`）
- ✅ 模糊/锐化（`setBlurSharpen()`）
- ✅ 颜色反转（`setInverted()`）
- ✅ HDR 色调映射（`setHighDynamicRange()`）
- ✅ F7 快捷键切换 Bloom

### ⬜ Phase 8 — 地形系统 `src/terrain.py` ⭐⭐⭐ **待实现**
> **引擎能力**：`ShaderTerrainMesh` + 高度图
>
> **依赖**：需要 16-bit PNG 高度图资源 + 地形纹理

- ⬜ 高度图加载 + 地形网格生成
- ⬜ 地形纹理混合（草地/泥土/岩石）
- ⬜ 与 Bullet 物理系统集成（地形碰撞体）
- ⬜ 地形 LOD 自适应

### ⬜ Phase 9 — 水面效果 `src/water.py` ⭐⭐⭐ **待实现**
> **引擎能力**：Shader + 渲染到纹理 + 扭曲
>
> **依赖**：需要自定义 GLSL Shader 文件

- ⬜ 平面水面 + 波纹动画
- ⬜ 简单反射效果（渲染到纹理）
- ⬜ 折射扭曲
- ⬜ 透明度 + 颜色可调

### ✅ Phase 10 — 日夜循环 `src/day_night.py` ⭐⭐ **已完成**
> **引擎能力**：动态光照参数 + 颜色插值

- ✅ 太阳方向随时间旋转（360° 循环）
- ✅ 光照颜色渐变（午夜深蓝 → 日出橙红 → 正午白色 → 日落橙色）
- ✅ 天空盒颜色联动
- ✅ 雾效颜色联动
- ✅ 时间加速/暂停控制（T 键）

### ✅ Phase 11 — NPC / AI `src/npc.py` ⭐⭐ **已完成**
> **引擎能力**：`Task` + 路径点 + FSM

- ✅ NPC 模型加载 + 巡逻路径（2 个默认 NPC）
- ✅ 状态：巡逻 → 发现玩家 → 追逐 → 返回
- ✅ 视野范围检测（`detect_range` 参数）
- ✅ N 键切换 NPC 可见性

### ✅ Phase 12 — 存档系统 `src/save_load.py` ⭐ **已完成**
> **引擎能力**：Python 标准库

- ✅ 保存：玩家位置、经验值、方块状态、日夜时间
- ✅ JSON 格式存档（`~/.my_game/save.json`）
- ✅ F5 快速保存 / F9 快速加载
- ✅ 系统消息提示保存/加载结果

### ✅ Phase 13 — 小地图 `src/minimap.py` ⭐⭐ **已完成**
> **引擎能力**：`base.makeCamera()` + `DisplayRegion`

- ✅ 独立正交相机俯视渲染
- ✅ 独立 `DisplayRegion` 右下角显示
- ✅ 玩家位置标记（红色圆形，程序化几何体 triangle fan）
- ✅ M 键切换小地图显示

### ✅ Phase 14 — 游戏状态机 `src/game_fsm.py` ⭐⭐ **已完成**
> **引擎能力**：`direct.fsm.FSM`

- ✅ 状态：Menu → Playing → Paused → GameOver
- ✅ 主菜单界面（DirectGUI）
- ✅ 暂停菜单（P 键）
- ✅ 游戏结束画面

### ✅ Phase 15 — NPC 对话框 `src/dialogue.py` ⭐ **已完成** (v0.7.0)
> **引擎能力**：`DirectGUI` + Python `random`

- ✅ NPC 进入追逐状态时触发对话
- ✅ 随机生成 20 个中文字符
- ✅ 屏幕底部对话框（`DirectFrame` + `OnscreenText`）
- ✅ 4 秒自动隐藏

### ✅ Phase 16 — ESC 退出确认 `src/exit_dialog.py` ⭐ **已完成** (v0.7.0)
> **引擎能力**：`DirectGUI` 模态对话框

- ✅ 半透明全屏遮罩
- ✅ 三个选项：存档并退出 / 直接退出 / 继续游戏
- ✅ 弹出时自动暂停，关闭时自动恢复
- ✅ 再按 ESC 等同于"继续游戏"

### ✅ Phase 17 — 快捷键标签页 + WASD 修复 ⭐ **已完成** (v0.7.0)

- ✅ 设置面板新增"⌨ 快捷键"Tab（25 个快捷键一览）
- ✅ WASD 方向基于相机前方/右方向量正确旋转
- ✅ 模型朝向修复（+180° 偏移适配熊猫模型）
- ✅ 切换视角后方向自动跟随

---

## 📅 实施优先级排序

```
Phase 1  ─ 阴影系统        ████████████████████ 高优先 · 视觉提升最大
Phase 5  ─ Interval 动画   ████████████████████ 高优先 · 基础设施
Phase 7  ─ 后处理滤镜      ████████████████████ 高优先 · 视觉提升大
Phase 14 ─ 游戏状态机 FSM  ████████████████████ 高优先 · 架构基础
Phase 3  ─ 雾效            ██████████████████   中优先 · 简单高效
Phase 2  ─ 粒子特效        ██████████████████   中优先 · 游戏感提升
Phase 10 ─ 日夜循环        ██████████████████   中优先 · 氛围感
Phase 4  ─ 天空盒          ██████████████████   中优先 · 环境完善
Phase 12 ─ 存档系统        ██████████████████   中优先 · 游戏完整性
Phase 11 ─ NPC / AI        ████████████████     中优先 · 游戏性
Phase 6  ─ 原生碰撞        ████████████████     中优先 · 引擎演示
Phase 13 ─ 小地图          ██████████████       低优先 · 锦上添花
Phase 8  ─ 地形系统        ██████████████       低优先 · 需要资源
Phase 9  ─ 水面效果        ██████████████       低优先 · 需要 Shader
```

---

## 🔧 每个 Phase 的文件变更

| Phase | 新增文件 | 修改文件 |
|-------|---------|---------|
| 1 | `src/shadows.py` | `src/scene.py`, `src/settings_panel.py` |
| 2 | `src/particles_fx.py`, `assets/particles/*.ptf` | `src/player.py`, `main.py` |
| 3 | `src/fog.py` | `src/settings_panel.py`, `main.py` |
| 4 | `src/skybox.py` | `src/scene.py`, `main.py` |
| 5 | `src/animations.py` | `src/hud.py`, `src/camera.py`, `main.py` |
| 6 | `src/collision.py` | `src/scene.py`, `main.py` |
| 7 | `src/post_processing.py` | `src/settings_panel.py`, `main.py` |
| 8 | `src/terrain.py`, `assets/textures/*` | `src/scene.py`, `main.py` |
| 9 | `src/water.py` | `src/scene.py`, `main.py` |
| 10 | `src/day_night.py` | `src/scene.py`, `src/skybox.py`, `main.py` |
| 11 | `src/npc.py` | `main.py`, `src/hud.py` |
| 12 | `src/save_load.py` | `main.py`, `src/settings_panel.py` |
| 13 | `src/minimap.py` | `main.py` |
| 14 | `src/game_fsm.py` | `main.py` |
| 15 | `src/dialogue.py` | `src/npc.py`, `main.py` |
| 16 | `src/exit_dialog.py` | `main.py` |
| 17 | — | `src/settings_panel.py`, `src/player.py`, `src/minimap.py` |

---

## 📝 版本规划

| 版本 | Phase | 里程碑 | 状态 |
|------|-------|--------|------|
| v0.6.0 | 1–7, 10–14 | 阴影 · 粒子 · 雾效 · 天空盒 · 动画 · 碰撞 · 后处理 · 日夜 · NPC · 存档 · 小地图 · FSM | ✅ 已发布 |
| v0.7.0 | 15–17 | NPC 对话框 · ESC 退出确认 · 快捷键 Tab · WASD 修复 · 代码重构 | ✅ 已发布 |
| v0.8.0 | 8 | 地形系统（需要高度图资源） | 📋 计划中 |
| v0.9.0 | 9 | 水面效果（需要 GLSL Shader） | 📋 计划中 |
