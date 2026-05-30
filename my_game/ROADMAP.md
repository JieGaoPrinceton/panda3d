# 🗺️ My Panda3D Game — 功能 Roadmap

> **基于 Panda3D 引擎能力 vs my_game 现有实现的差距分析**
>
> 最后更新：2026-05-30 · **v0.6.0**

---

## 📊 功能对比矩阵

### ✅ 已实现功能（my_game v0.6.0）

| 功能 | 模块 | 引擎对应 | 版本 |
|------|------|---------|------|
| Bullet 物理引擎 | `src/physics.py` | `panda3d.bullet` | v0.2.0 |
| 玩家移动 + 跳跃 | `src/player.py` | `BulletRigidBodyNode` | v0.1.0 |
| 轨道/第一/第三人称相机 | `src/camera.py` | `Camera` + 手动计算 | v0.2.0 |
| 音效系统 | `src/audio.py` | `AudioManager` + OpenAL | v0.3.0 |
| 鼠标射线拾取 | `src/picking.py` | `Bullet.rayTestClosest` | v0.3.0 |
| 经验值 + 可拾取物 | `src/collectibles.py` | 自定义逻辑 | v0.5.0 |
| 场景 + 光照 | `src/scene.py` | `AmbientLight` + `DirectionalLight` | v0.2.0 |
| HUD + 中文字体 | `src/hud.py` | `OnscreenText` | v0.2.0 |
| 设置面板 | `src/settings_panel.py` | `DirectGUI` | v0.2.0 |
| Actor 骨骼动画 | `src/player.py` | `direct.actor.Actor` | v0.1.0 |
| 物理调试渲染 | `src/physics.py` | `BulletDebugNode` | v0.2.0 |
| **阴影渲染** | `src/shadows.py` | `DirectionalLight.setShadowCaster()` | **v0.6.0** |
| **粒子特效** | `src/particles_fx.py` | `direct.particles.ParticleEffect` | **v0.6.0** |
| **雾效** | `src/fog.py` | `panda3d.core.Fog` | **v0.6.0** |
| **天空盒** | `src/skybox.py` | `GeomVertexData` + `CompassEffect` | **v0.6.0** |
| **Interval 动画** | `src/animations.py` | `direct.interval.*` | **v0.6.0** |
| **原生碰撞系统** | `src/collision.py` | `CollisionTraverser` + `CollisionHandlerEvent` | **v0.6.0** |
| **后处理滤镜** | `src/post_processing.py` | `direct.filter.CommonFilters` | **v0.6.0** |
| **日夜循环** | `src/day_night.py` | 动态光照 + 颜色插值 | **v0.6.0** |
| **NPC / AI 巡逻** | `src/npc.py` | `Task` + 路径点 + 状态机 | **v0.6.0** |
| **存档 / 读档** | `src/save_load.py` | Python `json` | **v0.6.0** |
| **小地图** | `src/minimap.py` | `Camera` + `DisplayRegion` | **v0.6.0** |
| **游戏状态机 FSM** | `src/game_fsm.py` | `direct.fsm.FSM` | **v0.6.0** |

### ❌ 尚未实现功能（引擎支持但 my_game 未 demo）

| # | 功能 | 引擎模块 / 示例 | 优先级 | 难度 | 状态 |
|---|------|----------------|--------|------|------|
| 1 | **Shader 地形** | `samples/shader-terrain/` · `ShaderTerrainMesh` | 🟡 中 | ⭐⭐⭐ | 📋 计划中 |
| 2 | **水面效果** | 引擎 Shader · `distortion` 示例 | 🟢 低 | ⭐⭐⭐ | 📋 计划中 |
| 3 | **点光源 / 聚光灯** | `samples/disco-lights/` · `PointLight` · `Spotlight` | 🟡 中 | ⭐ | 📋 计划中 |
| 4 | **法线贴图 / Bump Mapping** | `samples/bump-mapping/` · `Shader` | 🟢 低 | ⭐⭐⭐ | 📋 计划中 |
| 5 | **卡通渲染 Toon Shader** | `samples/cartoon-shader/` · `LightRampAttrib` | 🟢 低 | ⭐⭐⭐ | 📋 计划中 |
| 6 | **运动拖尾** | `samples/motion-trails/` · `MotionTrail` | 🟢 低 | ⭐⭐ | 📋 计划中 |
| 7 | **渲染到纹理 RTT** | `samples/render-to-texture/` · `makeTextureBuffer` | 🟢 低 | ⭐⭐ | 📋 计划中 |
| 8 | **程序化几何体** | `samples/procedural-cube/` · `GeomVertexData` | 🟢 低 | ⭐⭐ | 📋 计划中 |
| 9 | **手柄 / Gamepad 输入** | `samples/gamepad/` · `InputDevice` | 🟢 低 | ⭐⭐ | 📋 计划中 |
| 10 | **视频 / 媒体播放** | `samples/media-player/` · `MovieTexture` | 🟢 低 | ⭐ | 📋 计划中 |
| 11 | **遮挡剔除** | `samples/culling/` · `OccluderNode` | 🟢 低 | ⭐⭐ | 📋 计划中 |
| 12 | **网络多人** | `samples/networking/` · `direct.distributed` | 🟢 低 | ⭐⭐⭐⭐ | 📋 计划中 |
| 13 | **关节操控 / IK** | `samples/looking-and-gripping/` · `exposeJoint` | 🟢 低 | ⭐⭐ | 📋 计划中 |
| 14 | **材质系统** | `panda3d.core.Material` | 🟡 中 | ⭐ | 📋 计划中 |

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
- ✅ 玩家位置标记（红色方块）
- ✅ M 键切换小地图显示

### ✅ Phase 14 — 游戏状态机 `src/game_fsm.py` ⭐⭐ **已完成**
> **引擎能力**：`direct.fsm.FSM`

- ✅ 状态：Menu → Playing → Paused → GameOver
- ✅ 主菜单界面（DirectGUI）
- ✅ 暂停菜单（P 键）
- ✅ 游戏结束画面

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

---

## 📝 版本规划

| 版本 | Phase | 里程碑 | 状态 |
|------|-------|--------|------|
| v0.6.0 | 1–7, 10–14 | 阴影 · 粒子 · 雾效 · 天空盒 · 动画 · 碰撞 · 后处理 · 日夜 · NPC · 存档 · 小地图 · FSM | ✅ 已发布 |
| v0.7.0 | 8 | 地形系统（需要高度图资源） | 📋 计划中 |
| v0.8.0 | 9 | 水面效果（需要 GLSL Shader） | 📋 计划中 |
