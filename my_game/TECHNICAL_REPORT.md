# Panda3D 引擎代码结构技术报告

> **作者**: Zoo（AI 代码分析）  
> **日期**: 2026-05-30  
> **版本**: Panda3D master branch  
> **报告类型**: 科研级代码结构分析

---

## 目录

1. [项目总体架构](#1-项目总体架构)
2. [dtool — 基础工具层](#2-dtool--基础工具层)
3. [panda/src/pgraph — 场景图核心](#3-pandasrcpgraph--场景图核心)
4. [panda/src/display — 渲染管线与窗口系统](#4-pandasrcdisplay--渲染管线与窗口系统)
5. [panda/src/gobj — 几何对象层](#5-pandasrcgobj--几何对象层)
6. [panda/src/chan — 动画通道系统](#6-pandasrcchan--动画通道系统)
7. [panda/src/collide — 碰撞检测系统](#7-pandasrccollide--碰撞检测系统)
8. [panda/src/bullet — Bullet 物理集成](#8-pandasrcbullet--bullet-物理集成)
9. [panda/src/physics — 内置粒子物理](#9-pandasrcphysics--内置粒子物理)
10. [panda/src/egg — EGG 格式解析](#10-pandasrcegg--egg-格式解析)
11. [direct — Python 高层框架](#11-direct--python-高层框架)
12. [pandatool — 资产转换工具链](#12-pandatool--资产转换工具链)
13. [my_game — 示例游戏实现分析](#13-my_game--示例游戏实现分析)
14. [跨模块数据流与关键算法总结](#14-跨模块数据流与关键算法总结)
15. [参考文献与延伸阅读](#15-参考文献与延伸阅读)

### 图表列表

| 图号 | 标题 | 文件 |
|------|------|------|
| Fig.1 | 代码分层架构图 | [figures/fig1_architecture.svg](figures/fig1_architecture.svg) |
| Fig.2 | 渲染帧函数调用关系图 | [figures/fig2_render_pipeline.svg](figures/fig2_render_pipeline.svg) |
| Fig.3 | 场景图数据结构与类关系图 | [figures/fig3_scene_graph.svg](figures/fig3_scene_graph.svg) |
| Fig.4 | 动画系统类层次与调用关系图 | [figures/fig4_animation.svg](figures/fig4_animation.svg) |
| Fig.5 | 碰撞与物理系统对比图 | [figures/fig5_collision_physics.svg](figures/fig5_collision_physics.svg) |

---

## 1. 项目总体架构

Panda3D 是卡内基梅隆大学娱乐技术中心（ETC）开发的开源 3D 游戏引擎，采用 **C++ 核心 + Python 绑定** 的双层架构。整个代码库按功能分为四个顶层目录：

```
panda3d-master/
├── dtool/          # 基础工具层（配置系统、类型系统、内存管理）
├── panda/          # 引擎核心（场景图、渲染、物理、动画、碰撞）
├── direct/         # Python 高层框架（ShowBase、Task、FSM、Interval）
├── pandatool/      # 资产转换工具链（EGG/BAM/DAE/FBX 转换器）
└── my_game/        # 示例游戏（演示引擎各子系统的集成用法）
```

### 1.1 分层依赖关系

```
┌─────────────────────────────────────────────┐
│          my_game / 用户应用层                │
├─────────────────────────────────────────────┤
│          direct（Python 框架层）             │
│  ShowBase · Task · FSM · Interval · Actor   │
├─────────────────────────────────────────────┤
│          panda（C++ 引擎核心层）             │
│  pgraph · display · gobj · chan · collide   │
│  bullet · physics · egg · audio · text      │
├─────────────────────────────────────────────┤
│          dtool（基础工具层）                 │
│  prc · dconfig · dtoolbase · interrogatedb  │
└─────────────────────────────────────────────┘
```

### 1.2 构建系统

项目使用 **CMake** 作为主构建系统（`CMakeLists.txt`），同时保留了传统的 `makepanda/makepanda.py` Python 构建脚本。`cmake/modules/` 目录包含 30+ 个 `Find*.cmake` 模块，用于检测可选依赖（Bullet、FFMPEG、OpenCV、VRPN 等）。

> **Fig.1** — 代码分层架构全景图，展示从 OS/硬件到用户应用的五层依赖关系。
>
> ![Fig.1 代码分层架构图](figures/fig1_architecture.svg)

---

## 2. dtool — 基础工具层

**路径**: [`dtool/src/`](dtool/src/)

dtool 是整个引擎的地基，提供与平台无关的基础设施。

### 2.1 prc — 运行时配置系统

**核心文件**: [`dtool/src/prc/configVariable.h`](dtool/src/prc/configVariable.h)

Panda3D 的配置系统基于 `.prc` 文本文件，支持运行时读取与覆盖。

**核心类层次**:
```
ConfigVariableBase
  └── ConfigVariable          # 通用无类型变量
        ├── ConfigVariableBool
        ├── ConfigVariableInt
        ├── ConfigVariableDouble
        ├── ConfigVariableString
        └── ConfigVariableFilename
```

**算法要点**:
- 配置变量采用**懒加载**策略：首次访问时才从 `ConfigPage` 中查找对应声明
- 支持多层覆盖（系统级 → 用户级 → 命令行），优先级由 `ConfigPage` 的 `trust_level` 决定
- `ConfigVariableManager` 维护全局变量注册表，支持运行时枚举所有配置项

**示例用法**（引擎内部）:
```cpp
ConfigVariableInt PhysicsManager::_random_seed("physics_manager_random_seed", 139);
ConfigVariableBool fake_view_frustum_cull("fake-view-frustum-cull", false);
```

### 2.2 dtoolbase — 内存与类型基础

提供 `TypedObject`（运行时类型识别 RTTI）、`ReferenceCount`（引用计数智能指针基类）、`PointerTo<T>` / `ConstPointerTo<T>` 等核心基础设施。

### 2.3 interrogatedb — Python 绑定元数据

`interrogate` 工具扫描 C++ 头文件中的 `PUBLISHED:` 标记区域，自动生成 Python 绑定代码，这是 Panda3D 实现 C++/Python 无缝互操作的关键机制。

---

## 3. panda/src/pgraph — 场景图核心

**路径**: [`panda/src/pgraph/`](panda/src/pgraph/)

pgraph（Panda Graph）是引擎最核心的模块，实现了场景图数据结构、渲染状态管理和可见性裁剪。

### 3.1 PandaNode — 场景图节点基类

**核心文件**: [`panda/src/pgraph/pandaNode.h`](panda/src/pgraph/pandaNode.h)

```cpp
class PandaNode : public TypedWritableReferenceCount, public Namable {
  // 多线程安全的流水线数据（CycleData）
  PipelineCycler<CData> _cycler;
  // 渲染状态（不可变共享对象）
  CPT(RenderState) _state;
  // 变换状态（不可变共享对象）
  CPT(TransformState) _transform;
  // 绘制掩码（相机可见性过滤）
  DrawMask _draw_control_mask;
};
```

**设计要点**:
- 节点采用**多父节点**（instancing）设计：同一个 `PandaNode` 可以被多个 `NodePath` 引用
- 使用 `PipelineCycler` 实现**多线程流水线**：App 线程写入，Cull/Draw 线程读取，无锁竞争
- `fancy_bits` 位掩码快速判断节点是否需要特殊处理（边界框显示、遮挡剔除等）

### 3.2 NodePath — 场景图操作句柄

**核心文件**: [`panda/src/pgraph/nodePath.h`](panda/src/pgraph/nodePath.h)

`NodePath` 是用户与场景图交互的**主要接口**，封装了从根节点到目标节点的完整路径。

```
NodePath = (NodePathComponent链表) → PandaNode
```

**核心算法**:
- **路径解析**: 支持类似文件系统的路径字符串（`"**/ModelRoot/Geometry"`），使用 `FindApproxPath` + `FindApproxLevelEntry` 实现 BFS/DFS 搜索
- **变换合成**: `get_net_transform()` 沿路径向上累积所有 `TransformState`，利用缓存避免重复计算
- **状态继承**: `get_net_state()` 沿路径合成 `RenderState`，子节点状态覆盖父节点

### 3.3 RenderState — 不可变渲染状态

**核心文件**: [`panda/src/pgraph/renderState.cxx`](panda/src/pgraph/renderState.cxx)

`RenderState` 是一个**不可变（immutable）共享对象**，包含一组 `RenderAttrib`（渲染属性）。

**关键算法 — 状态缓存与合成**:
```
RenderState::compose(other) → 查全局哈希表 _states
  ├── 命中缓存 → 直接返回
  └── 未命中 → 逐属性合成 → 插入缓存 → 返回
```

- 全局 `_states` 哈希表存储所有已创建的 `RenderState`，实现**结构共享**（structural sharing）
- 状态合成（compose）结果也被缓存，形成**组合缓存**（composition cache）
- 垃圾回收通过 `garbage_collect()` 定期清理引用计数为零的状态

**RenderAttrib 类型**（部分）:
| 属性类 | 功能 |
|--------|------|
| `TextureAttrib` | 纹理绑定 |
| `ShaderAttrib` | GLSL/Cg 着色器 |
| `ColorAttrib` | 顶点颜色模式 |
| `TransparencyAttrib` | 透明度混合 |
| `DepthTestAttrib` | 深度测试 |
| `CullFaceAttrib` | 背面剔除 |
| `LightAttrib` | 光照绑定 |
| `FogAttrib` | 雾效 |

### 3.4 CullTraverser — 可见性裁剪遍历器

**核心文件**: [`panda/src/pgraph/cullTraverser.cxx`](panda/src/pgraph/cullTraverser.cxx)

`CullTraverser` 实现了场景图的**视锥体裁剪**（View Frustum Culling）遍历。

**核心算法流程**:
```
traverse(root_node_path)
  ├── 构建 CullTraverserData（携带累积变换、状态、视锥体）
  ├── is_in_view(camera_mask) → 边界体与视锥体相交测试
  │     ├── 完全在外 → 剔除整棵子树
  │     ├── 完全在内 → 跳过子节点测试（优化）
  │     └── 部分相交 → 递归测试子节点
  └── do_traverse(data)
        ├── 处理 fancy_bits（边界框、遮挡、Portal 等）
        ├── 调用 node->cull_callback()（节点自定义裁剪逻辑）
        └── 将可见几何体提交给 CullHandler → CullBin
```

**Portal 裁剪**（可选）:
- 当 `allow_portal_cull = true` 时，使用 `PortalClipper` 进行**门户裁剪**
- 通过 Portal 节点定义房间连接关系，只渲染摄像机可见的房间

### 3.5 SceneGraphReducer — 场景图优化

**核心文件**: [`panda/src/pgraph/sceneGraphReducer.h`](panda/src/pgraph/sceneGraphReducer.h)

提供场景图**扁平化**（flattening）优化，通过合并相邻节点减少绘制调用（Draw Call）：

```
flatten_strong()  → 合并所有可合并节点（最激进）
flatten_medium()  → 合并相同状态的兄弟节点
flatten_light()   → 仅合并变换（最保守）
```

> **Fig.3** — 场景图数据结构与类关系图，展示 `PandaNode` 继承层次、`NodePath` 路径解析、`PipelineCycler` 多线程隔离机制。
>
> ![Fig.3 场景图数据结构图](figures/fig3_scene_graph.svg)

---

## 4. panda/src/display — 渲染管线与窗口系统

**路径**: [`panda/src/display/`](panda/src/display/)

### 4.1 GraphicsEngine — 渲染引擎主控

**核心文件**: [`panda/src/display/graphicsEngine.cxx`](panda/src/display/graphicsEngine.cxx)

`GraphicsEngine` 是渲染系统的**总调度器**，管理所有窗口、缓冲区和渲染线程。

**每帧渲染流程** (`render_frame()`):
```
render_frame()
  ├── 1. App 线程：推进 Pipeline（cycler advance）
  ├── 2. Cull 线程：对每个 DisplayRegion 执行 CullTraverser
  │     └── 输出 CullResult（按 CullBin 排序的可见几何体列表）
  ├── 3. Draw 线程：GraphicsStateGuardian 执行实际 GPU 绘制
  │     ├── 遍历 CullBin（按 sort 值排序）
  │     ├── 对每个 CullableObject 调用 draw_*() 方法
  │     └── 状态差分更新（只提交变化的 RenderState）
  └── 4. Flip：交换前后缓冲区
```

**线程模型**（`GraphicsThreadingModel`）:
| 模型字符串 | 描述 |
|-----------|------|
| `""` | 单线程（App/Cull/Draw 同线程） |
| `"Cull/Draw"` | Cull 与 Draw 分离线程 |
| `"App/Cull/Draw"` | 三线程流水线 |

### 4.2 GraphicsStateGuardian (GSG) — 渲染后端抽象

**核心文件**: [`panda/src/display/graphicsStateGuardian.h`](panda/src/display/graphicsStateGuardian.h)

GSG 是渲染后端的**抽象接口**，封装了所有 GPU API 调用。

**核心职责**:
- **状态守卫**（State Guardian）：跟踪当前 GPU 状态，避免冗余状态切换
- **资源管理**：通过 `PreparedGraphicsObjects` 管理纹理、顶点缓冲、着色器的 GPU 资源生命周期
- **着色器生成**：`ShaderGenerator` 根据 `RenderState` 自动生成 GLSL 着色器（Auto Shader）

**具体实现**:
| 子类 | 后端 |
|------|------|
| `GLGraphicsStateGuardian` | OpenGL |
| `GLES2GraphicsStateGuardian` | OpenGL ES 2.0 |
| `DXGraphicsStateGuardian9` | Direct3D 9 |
| `TinyGraphicsStateGuardian` | 软件渲染 |

### 4.3 DisplayRegion — 视口管理

`DisplayRegion` 定义了窗口中的一个矩形渲染区域，关联一个 `Camera` 节点。支持**立体渲染**（`StereoDisplayRegion`）和**多视口**布局。

---

## 5. panda/src/gobj — 几何对象层

**路径**: [`panda/src/gobj/`](panda/src/gobj/)

### 5.1 Geom — 几何体容器

**核心文件**: [`panda/src/gobj/geom.h`](panda/src/gobj/geom.h)

`Geom` 是几何数据的核心容器，将**顶点数据**（`GeomVertexData`）与**图元**（`GeomPrimitive`）绑定：

```
Geom
  ├── GeomVertexData          # 顶点属性表（位置、法线、UV、颜色等）
  │     └── GeomVertexArrayData[]  # 每个数组对应一个 VBO
  └── GeomPrimitive[]         # 图元列表
        ├── GeomTriangles     # 三角形列表
        ├── GeomTristrips     # 三角形条带
        ├── GeomLines         # 线段
        └── GeomPoints        # 点
```

**Copy-on-Write 机制**:
- `Geom` 继承自 `CopyOnWriteObject`，多个节点共享同一 `Geom` 时不复制数据
- 修改时触发 COW，保证线程安全

### 5.2 GeomVertexData — 顶点数据格式

采用**列式存储**（Structure of Arrays）设计，每个顶点属性（position、normal、texcoord 等）存储在独立的 `GeomVertexArrayData` 中，对应 GPU 端的 VBO。

`GeomVertexFormat` 描述顶点布局，支持运行时动态格式转换（`GeomMunger`）。

> **Fig.2** — 渲染帧三线程流水线函数调用图，展示 App/Cull/Draw 线程的完整调用链。
>
> ![Fig.2 渲染帧函数调用关系图](figures/fig2_render_pipeline.svg)

---

## 6. panda/src/chan — 动画通道系统

**路径**: [`panda/src/chan/`](panda/src/chan/)

### 6.1 整体架构

Panda3D 的骨骼动画系统基于**通道（Channel）**概念：

```
PartBundle（骨骼层次根）
  └── MovingPartMatrix[]（骨骼关节）
        └── AnimControl（动画控制器）
              ├── AnimBundle（动画数据根）
              │     └── AnimChannelMatrixXfmTable（关键帧数据）
              └── 播放状态（帧号、速率、循环）
```

### 6.2 PartBundle — 骨骼层次根

**核心文件**: [`panda/src/chan/partBundle.h`](panda/src/chan/partBundle.h)

`PartBundle` 是可动角色的骨骼层次根节点，管理所有动画混合。

**混合类型** (`BlendType`):
| 枚举值 | 算法 |
|--------|------|
| `BT_linear` | 矩阵线性插值（可能产生拉伸） |
| `BT_normalized_linear` | 归一化线性插值（改善拉伸） |
| `BT_componentwise` | 分量独立插值（位移/旋转/缩放分别插值） |
| `BT_componentwise_quat` | 四元数球面线性插值（SLERP，最高质量） |

**多动画混合算法**:
```
ChannelBlend = map<AnimControl*, weight>  // 权重归一化
do_update():
  for each MovingPart:
    matrix = Σ(channel_i.get_value(frame) * weight_i)  // 加权平均
    apply_matrix_to_joint()
```

### 6.3 AnimControl — 动画控制器

**核心文件**: [`panda/src/chan/animControl.h`](panda/src/chan/animControl.h)

`AnimControl` 管理单个动画的播放状态，继承自 `AnimInterface`（提供 `play()`、`loop()`、`stop()`、`pose()` 等接口）。

**帧混合**（Frame Blending）:
- 当 `frame_blend_flag = true` 时，在相邻关键帧之间进行线性插值，消除动画抖动
- `channel_has_changed()` 检测通道值是否变化，避免不必要的矩阵更新

### 6.4 AnimChannelMatrixXfmTable — 关键帧数据

**核心文件**: [`panda/src/chan/animChannelMatrixXfmTable.h`](panda/src/chan/animChannelMatrixXfmTable.h)

存储每个关节的变换关键帧数据，分解为 9 个独立通道：
`i, j, k`（缩放）、`a, b, c`（剪切）、`h, p, r`（旋转 HPR）、`x, y, z`（位移）

> **Fig.4** — 动画系统类层次与调用关系图，展示从 `Actor.loop()` 到 GPU 蒙皮变换的完整调用链及 SLERP 混合算法。
>
> ![Fig.4 动画系统类层次图](figures/fig4_animation.svg)

---

## 7. panda/src/collide — 碰撞检测系统

**路径**: [`panda/src/collide/`](panda/src/collide/)

### 7.1 CollisionTraverser — 碰撞遍历器

**核心文件**: [`panda/src/collide/collisionTraverser.cxx`](panda/src/collide/collisionTraverser.cxx)

`CollisionTraverser` 实现了 Panda3D 内置的**窄相碰撞检测**系统（区别于 Bullet 的宽相+窄相）。

**算法流程**:
```
traverse(root)
  ├── 收集所有 CollisionNode（碰撞体节点）
  ├── 对每个 collider（主动碰撞体）:
  │     ├── 遍历场景图中所有 into_node（被动碰撞体）
  │     ├── 边界体快速排除（BoundingSphere 相交测试）
  │     └── 精确碰撞测试（CollisionSolid::test_intersection()）
  └── 触发 CollisionHandler 回调
```

**碰撞体类型**:
| 类 | 形状 | 用途 |
|----|------|------|
| `CollisionSphere` | 球体 | 最快，角色碰撞 |
| `CollisionBox` | 轴对齐包围盒 | 静态障碍物 |
| `CollisionCapsule` | 胶囊体 | 角色控制器 |
| `CollisionRay` | 射线 | 地面检测、拾取 |
| `CollisionPlane` | 无限平面 | 地面边界 |
| `CollisionPolygon` | 任意多边形 | 精确地形 |
| `CollisionHeightfield` | 高度场 | 地形碰撞 |

### 7.2 CollisionHandler — 碰撞响应

| 处理器类 | 行为 |
|---------|------|
| `CollisionHandlerEvent` | 发送 Panda3D 事件 |
| `CollisionHandlerPusher` | 推开碰撞体（防穿透） |
| `CollisionHandlerFloor` | 角色站在地面上 |
| `CollisionHandlerGravity` | 重力 + 地面吸附 |
| `CollisionHandlerQueue` | 收集碰撞结果供查询 |

> **Fig.5** — 内置碰撞系统与 Bullet 物理系统对比图，展示两套系统的架构差异、算法流程与适用场景。
>
> ![Fig.5 碰撞与物理系统对比图](figures/fig5_collision_physics.svg)

---

## 8. panda/src/bullet — Bullet 物理集成

**路径**: [`panda/src/bullet/`](panda/src/bullet/)

### 8.1 BulletWorld — 物理世界

**核心文件**: [`panda/src/bullet/bulletWorld.cxx`](panda/src/bullet/bulletWorld.cxx)

Panda3D 的 Bullet 集成将 **Bullet Physics SDK** 封装为 Panda3D 风格的 API。

**初始化流程**:
```cpp
BulletWorld():
  // 宽相（Broadphase）
  _broadphase = new btAxisSweep3(...)      // SAP 算法
              | new btDbvtBroadphase()     // 动态 AABB 树
  // 碰撞配置
  _configuration = new btSoftBodyRigidBodyCollisionConfiguration()
  // 窄相调度器
  _dispatcher = new btCollisionDispatcher(_configuration)
  // 约束求解器
  _solver = new btSequentialImpulseConstraintSolver()
  // 动力学世界
  _world = new btSoftRigidDynamicsWorld(...)
```

**每帧更新** (`do_physics(dt)`):
```
SyncP2B: Panda3D 场景图变换 → Bullet 刚体变换
Simulation: _world->stepSimulation(dt, max_substeps, fixed_timestep)
SyncB2P: Bullet 刚体变换 → Panda3D 场景图变换
```

**PStats 性能监控**:
- `App:Bullet:DoPhysics` — 总物理时间
- `App:Bullet:DoPhysics:Simulation` — Bullet 仿真时间
- `App:Bullet:DoPhysics:SyncP2B/SyncB2P` — 同步时间

### 8.2 碰撞形状

| 形状类 | Bullet 对应 | 特点 |
|--------|------------|------|
| `BulletSphereShape` | `btSphereShape` | 最快 |
| `BulletBoxShape` | `btBoxShape` | AABB |
| `BulletCapsuleShape` | `btCapsuleShape` | 角色控制器 |
| `BulletPlaneShape` | `btStaticPlaneShape` | 无限地面 |
| `BulletTriangleMeshShape` | `btBvhTriangleMeshShape` | 精确静态网格 |
| `BulletHeightfieldShape` | `btHeightfieldTerrainShape` | 地形 |

---

## 9. panda/src/physics — 内置粒子物理

**路径**: [`panda/src/physics/`](panda/src/physics/)

### 9.1 PhysicsManager — 力学管理器

**核心文件**: [`panda/src/physics/physicsManager.cxx`](panda/src/physics/physicsManager.cxx)

Panda3D 内置了一个轻量级的**粒子物理系统**（区别于 Bullet），主要用于粒子特效。

**架构**:
```
PhysicsManager
  ├── LinearIntegrator（线性积分器）
  │     └── EulerIntegrator（默认：欧拉积分）
  ├── AngularIntegrator（角速度积分器）
  ├── LinearForce[]（全局线性力：重力、风力等）
  └── Physical[]（物理对象列表）
        └── PhysicsObject（质点：位置、速度、质量）
```

**积分算法**（欧拉法）:
```
v(t+dt) = v(t) + F/m * dt
x(t+dt) = x(t) + v(t+dt) * dt
```

---

## 10. panda/src/egg — EGG 格式解析

**路径**: [`panda/src/egg/`](panda/src/egg/)

### 10.1 EggData — EGG 文件根节点

**核心文件**: [`panda/src/egg/eggData.h`](panda/src/egg/eggData.h)

EGG（`.egg`）是 Panda3D 的原生文本格式，类似于简化版的 VRML/X3D。

**EGG 文件结构**（树形）:
```
EggData (根)
  ├── EggCoordinateSystem
  ├── EggTexture[]          # 纹理声明
  ├── EggMaterial[]         # 材质声明
  ├── EggGroup[]            # 节点组（对应场景图节点）
  │     ├── EggPolygon[]    # 多边形面
  │     └── EggVertex[]     # 顶点
  └── EggTable[]            # 动画数据
        └── EggXfmSAnim     # 变换动画通道
```

**BAM 格式**（Binary Animation Model）:
- `.bam` 是 EGG 的二进制编译版本，加载速度比 EGG 快 10-100 倍
- `BamFile` / `BamReader` / `BamWriter` 实现序列化/反序列化

---

## 11. direct — Python 高层框架

**路径**: [`direct/src/`](direct/src/)

### 11.1 ShowBase — 应用程序框架

**核心文件**: [`direct/src/showbase/ShowBase.py`](direct/src/showbase/ShowBase.py)

`ShowBase` 是 Panda3D Python 应用的**入口框架**，初始化时完成以下工作：

```python
ShowBase.__init__():
  1. 创建 GraphicsEngine（渲染引擎）
  2. 创建 GraphicsPipe（平台窗口管道）
  3. 创建主窗口 GraphicsWindow
  4. 建立场景图根节点：
     - render        # 3D 主场景根
     - render2d      # 2D 覆盖层根（-1~1 坐标）
     - aspect2d      # 保持宽高比的 2D 层
     - pixel2d       # 像素坐标 2D 层
  5. 创建默认相机（base.camera）
  6. 启动 TaskManager 主循环
  7. 注册全局变量到 builtins（base, render, camera 等）
```

**全局变量注入**（写入 `builtins` 模块）:
```python
builtins.base      = self          # ShowBase 实例
builtins.render    = self.render   # 3D 场景根
builtins.camera    = self.camera   # 主相机
builtins.loader    = self.loader   # 资源加载器
builtins.taskMgr   = taskMgr       # 任务管理器
builtins.messenger = messenger     # 消息系统
```

### 11.2 TaskManager — 协作式任务调度

**核心文件**: [`direct/src/task/Task.py`](direct/src/task/Task.py)

`TaskManager` 是 Panda3D 的**主循环调度器**，基于 C++ `AsyncTaskManager` 实现。

**任务返回值语义**:
| 返回值 | 行为 |
|--------|------|
| `Task.cont` | 继续执行（下帧再调用） |
| `Task.done` | 任务完成，移除 |
| `Task.again` | 重新调度（用于延迟任务） |

**协程支持**（Python 3.5+）:
```python
async def my_task(task):
    await asyncio.sleep(1.0)   # 非阻塞等待
    return task.done
```

**内置任务链**（按 sort 值排序）:
```
sort=-50: igLoop（输入事件处理）
sort=0:   dataLoop（数据图遍历）
sort=20:  collisionLoop（碰撞检测）
sort=35:  audioLoop（音频更新）
sort=45:  igLoop（渲染帧）
sort=50:  ivalLoop（Interval 更新）
```

### 11.3 FSM — 有限状态机

**核心文件**: [`direct/src/fsm/FSM.py`](direct/src/fsm/FSM.py)

Panda3D 的 FSM 采用**隐式状态定义**：通过方法命名约定（`enterXxx` / `exitXxx`）定义状态行为，无需显式注册状态。

**核心算法**:
```python
FSM.request(state_name):
  1. 检查 _filter_map 是否允许此转换
  2. 调用 exitOldState()（当前状态退出回调）
  3. 更新 self.state
  4. 调用 enterNewState()（新状态进入回调）
  5. 支持 async 状态（返回 Transition future）
```

**转换过滤**（`defaultFilter`）:
- 默认允许从任意状态转换到任意状态
- 子类可重写 `filterXxx(request, args)` 限制转换规则

### 11.4 Interval — 时间线动画系统

**核心文件**: [`direct/src/interval/Interval.py`](direct/src/interval/Interval.py)

`Interval` 是 Panda3D 的**时间线动画**系统，类似于 Flash/CSS 的 Tween。

**Interval 类型**:
| 类 | 功能 |
|----|------|
| `LerpPosInterval` | 位置插值动画 |
| `LerpHprInterval` | 旋转插值动画 |
| `LerpScaleInterval` | 缩放插值动画 |
| `LerpColorInterval` | 颜色插值动画 |
| `SoundInterval` | 音频播放 |
| `FunctionInterval` | 任意函数调用 |
| `Sequence` | 串行序列 |
| `Parallel` | 并行序列 |
| `Wait` | 等待延迟 |

**核心算法**（`setT(t)`）:
```python
setT(t):
  # 将时间 t 映射到 [startT, endT] 区间
  # 调用 privStep(t) 执行实际插值
  # 线性插值: value = start + (end - start) * (t / duration)
```

**C++ 加速**：核心 `CInterval` 类在 C++ 中实现（`panda3d.direct.CInterval`），Python 层仅做薄封装。

### 11.5 Actor — 骨骼动画角色

**核心文件**: [`direct/src/actor/Actor.py`](direct/src/actor/Actor.py)

`Actor` 是对 `PartBundle`（C++ 骨骼系统）的 Python 封装，提供高层动画控制接口。

```python
actor = Actor("panda-model", {"walk": "panda-walk4"})
actor.loop("walk")                              # 循环播放
actor.play("walk", fromFrame=0, toFrame=10)     # 播放片段
actor.blendAnim("walk", 0.5)                    # 混合权重
actor.controlJoint(None, "modelRoot", "Hips")   # 程序化骨骼控制
```

### 11.6 Messenger — 事件消息系统

**核心文件**: [`direct/src/showbase/Messenger.py`](direct/src/showbase/Messenger.py)

基于**发布-订阅**（Pub/Sub）模式的事件系统：

```python
messenger.accept("event-name", handler_func)  # 订阅
messenger.send("event-name", [args])           # 发布
messenger.ignore("event-name")                 # 取消订阅
```

---

## 12. pandatool — 资产转换工具链

**路径**: [`pandatool/src/`](pandatool/src/)

### 12.1 工具分类

| 目录 | 工具 | 功能 |
|------|------|------|
| `eggprogs/` | `egg-trans` | EGG 格式变换/优化 |
| `egg-optchar/` | `egg-optchar` | 角色模型优化（合并关节） |
| `egg-palettize/` | `egg-palettize` | 纹理图集打包 |
| `egg-mkfont/` | `egg-mkfont` | 字体转 EGG |
| `egg-qtess/` | `egg-qtess` | NURBS 曲面细分 |
| `daeegg/` | `dae2egg` | COLLADA → EGG |
| `assimp/` | `assimp2egg` | 多格式 → EGG（FBX/OBJ/3DS） |
| `bam/` | `bam2egg`/`egg2bam` | EGG ↔ BAM 互转 |
| `flt/` | `flt2egg` | OpenFlight → EGG |
| `lwo/` | `lwo2egg` | LightWave → EGG |
| `xfile/` | `x2egg` | DirectX X → EGG |
| `pstatserver/` | `pstats` | 性能分析服务器 |
| `gtk-stats/` | GTK PStats | Linux 性能分析 GUI |
| `mac-stats/` | macOS PStats | macOS 性能分析 GUI |

### 12.2 DAE 角色转换

**核心文件**: [`pandatool/src/daeegg/daeCharacter.cxx`](pandatool/src/daeegg/daeCharacter.cxx)

`DaeCharacter` 处理 COLLADA 格式的骨骼动画转换：
- 解析 `<skin>` 元素提取骨骼权重
- 解析 `<animation>` 元素提取关键帧
- 将 COLLADA 坐标系转换为 Panda3D 坐标系（Y-up → Z-up）

---

## 13. my_game — 示例游戏实现分析

**路径**: [`my_game/src/`](my_game/src/)

示例游戏是一个完整的 3D 游戏 Demo，演示了 Panda3D 各子系统的集成用法。

### 13.1 模块依赖图

```
main.py
  ├── GameFSM           (game_fsm.py)       — 游戏状态机
  ├── PhysicsManager    (physics.py)        — Bullet 物理世界
  ├── SceneBuilder      (scene.py)          — 场景构建
  ├── PlayerController  (player.py)         — 玩家控制
  ├── OrbitCamera       (camera.py)         — 相机控制
  ├── HUD               (hud.py)            — 平视显示器
  ├── DayNightCycle     (day_night.py)      — 日夜循环
  ├── ShadowManager     (shadows.py)        — 阴影系统
  ├── SkyBox            (skybox.py)         — 天空盒
  ├── FogManager        (fog.py)            — 雾效
  ├── CollectibleManager(collectibles.py)   — 可收集物品
  ├── NPCManager        (npc.py)            — NPC 系统
  ├── MiniMap           (minimap.py)        — 小地图
  ├── SaveLoadManager   (save_load.py)      — 存档系统
  └── PostProcessing    (post_processing.py)— 后处理
```

### 13.2 PhysicsManager — Bullet 物理管理

**核心文件**: [`my_game/src/physics.py`](my_game/src/physics.py)

```python
PhysicsManager.__init__():
  world = BulletWorld()
  world.setGravity(Vec3(0, 0, -9.81))

  # 地面碰撞平面（无限平面，mass=0）
  ground_shape = BulletPlaneShape(Vec3(0, 0, 1), 0)
  ground_body  = BulletRigidBodyNode("ground")
  world.attachRigidBody(ground_body)

  # 调试渲染（F1 切换）
  debug_node = BulletDebugNode("bullet_debug")
  debug_node.showWireframe(True)
```

**每帧更新**:
```python
taskMgr.add(physics_update_task, "physics")
# physics_update_task:
world.doPhysics(dt, 10, 1/180)  # 最多10子步，固定步长1/180秒
```

### 13.3 PlayerController — 玩家控制

**核心文件**: [`my_game/src/player.py`](my_game/src/player.py)

**物理体设计**:
```python
# 球形碰撞体（简单高效）
shape = BulletSphereShape(0.5)
body  = BulletRigidBodyNode("player_physics")
body.setMass(80.0)
body.setAngularFactor(Vec3(0, 0, 0))  # 锁定旋转轴，防止翻滚
```

**移动算法**（WASD + 相机朝向）:
```python
heading_rad = math.radians(camera.heading)
move_dir = Vec3(
    math.sin(heading_rad) * forward - math.cos(heading_rad) * strafe,
    math.cos(heading_rad) * forward + math.sin(heading_rad) * strafe,
    0
)
body.setLinearVelocity(move_dir * speed + Vec3(0, 0, vz))
```

**跳跃检测**（Bullet 射线）:
```python
ray_from = player_pos
ray_to   = player_pos + Vec3(0, 0, -1.1)
result   = world.rayTestClosest(ray_from, ray_to)
is_grounded = result.hasHit()
```

### 13.4 OrbitCamera — 多模式相机

**核心文件**: [`my_game/src/camera.py`](my_game/src/camera.py)

**球坐标系相机位置计算**:
```python
# 第三人称相机位置（球坐标 → 笛卡尔坐标）
x = target.x + distance * cos(pitch_rad) * sin(heading_rad)
y = target.y - distance * cos(pitch_rad) * cos(heading_rad)
z = target.z + distance * sin(-pitch_rad) + height_offset
camera.setPos(x, y, z)
camera.lookAt(target)
```

**三种模式**（V 键循环切换）:
- `THIRD_PERSON`：跟随玩家，右键拖拽旋转
- `FIRST_PERSON`：玩家视角，右键拖拽看向，滚轮调 FOV
- `ORBIT`：自由轨道相机

### 13.5 GameFSM — 游戏状态机

**核心文件**: [`my_game/src/game_fsm.py`](my_game/src/game_fsm.py)

```
状态转换图:
  [Menu] ──startGame──→ [Playing]
  [Playing] ──pause──→ [Paused]
  [Paused] ──resume──→ [Playing]
  [Playing] ──gameOver──→ [GameOver]
  [GameOver] ──restart──→ [Menu]
```

每个状态的 `enterXxx()` 方法创建对应 UI，`exitXxx()` 方法销毁 UI，实现**状态隔离**。

---

## 14. 跨模块数据流与关键算法总结

### 14.1 完整渲染帧数据流

```
[App 线程]
  TaskManager.step()
    → 用户任务（移动、物理、动画更新）
    → Pipeline.cycle_data()（推进流水线）

[Cull 线程]
  GraphicsEngine.cull_and_draw_together() 或 cull_scene()
    → CullTraverser.traverse(render)
        → 视锥体裁剪（BoundingVolume 测试）
        → 状态合成（RenderState::compose）
        → 提交到 CullBin（按材质/深度排序）

[Draw 线程]
  GraphicsStateGuardian.draw_scene()
    → 遍历 CullBin（按 sort 值）
    → 状态差分更新（只提交变化的 RenderAttrib）
    → 调用 OpenGL/DX API 绘制
    → swap_buffers()
```

### 14.2 关键性能优化技术

| 技术 | 实现位置 | 原理 |
|------|---------|------|
| 视锥体裁剪 | [`CullTraverser`](panda/src/pgraph/cullTraverser.cxx) | 边界体与视锥体相交测试，剔除不可见子树 |
| 状态结构共享 | [`RenderState`](panda/src/pgraph/renderState.cxx) | 不可变对象 + 全局哈希缓存，避免重复创建 |
| 场景图扁平化 | [`SceneGraphReducer`](panda/src/pgraph/sceneGraphReducer.h) | 合并相同状态节点，减少 Draw Call |
| 流水线多线程 | [`PipelineCycler`](panda/src/pgraph/pandaNode.h) | App/Cull/Draw 三线程无锁流水线 |
| 顶点数据 COW | [`GeomVertexData`](panda/src/gobj/geom.h) | 写时复制，多节点共享顶点数据 |
| 动画帧混合 | [`AnimChannelMatrixXfmTable`](panda/src/chan/animChannelMatrixXfmTable.h) | 关键帧间线性插值，消除抖动 |
| Bullet 宽相 | [`BulletWorld`](panda/src/bullet/bulletWorld.cxx) | AABB 树/SAP 快速排除不相交对 |
| 状态差分渲染 | [`GraphicsStateGuardian`](panda/src/display/graphicsStateGuardian.h) | 只提交变化的 GPU 状态，减少 API 调用 |

### 14.3 C++/Python 互操作机制

```
C++ 源码（PUBLISHED: 标记区域）
    ↓ interrogate 工具扫描
生成 Python 绑定元数据（interrogatedb）
    ↓ 编译时生成
panda3d.core / panda3d.bullet 等 Python 扩展模块
    ↓ 运行时
Python 代码直接调用 C++ 对象方法（零拷贝）
```

### 14.4 配置系统数据流

```
.prc 文件（系统/用户/应用）
    ↓ ConfigPageManager 加载
ConfigPage（按 trust_level 排序）
    ↓ 查找
ConfigVariableCore（变量核心）
    ↓ 类型化包装
ConfigVariableBool / ConfigVariableInt / ConfigVariableString / ...
    ↓ 引擎内部使用
```

---

## 15. 参考文献与延伸阅读

### 15.1 核心源文件索引

| 模块 | 关键文件 | 核心类/函数 |
|------|---------|------------|
| 场景图节点 | [`panda/src/pgraph/pandaNode.h`](panda/src/pgraph/pandaNode.h) | `PandaNode` |
| 场景图句柄 | [`panda/src/pgraph/nodePath.h`](panda/src/pgraph/nodePath.h) | `NodePath` |
| 渲染状态 | [`panda/src/pgraph/renderState.cxx`](panda/src/pgraph/renderState.cxx) | `RenderState::compose()` |
| 可见性裁剪 | [`panda/src/pgraph/cullTraverser.cxx`](panda/src/pgraph/cullTraverser.cxx) | `CullTraverser::traverse()` |
| 渲染引擎 | [`panda/src/display/graphicsEngine.cxx`](panda/src/display/graphicsEngine.cxx) | `GraphicsEngine::render_frame()` |
| 渲染后端 | [`panda/src/display/graphicsStateGuardian.h`](panda/src/display/graphicsStateGuardian.h) | `GraphicsStateGuardian` |
| 几何体 | [`panda/src/gobj/geom.h`](panda/src/gobj/geom.h) | `Geom` |
| 骨骼根 | [`panda/src/chan/partBundle.h`](panda/src/chan/partBundle.h) | `PartBundle::do_update()` |
| 动画控制 | [`panda/src/chan/animControl.h`](panda/src/chan/animControl.h) | `AnimControl` |
| 碰撞遍历 | [`panda/src/collide/collisionTraverser.cxx`](panda/src/collide/collisionTraverser.cxx) | `CollisionTraverser::traverse()` |
| Bullet 世界 | [`panda/src/bullet/bulletWorld.cxx`](panda/src/bullet/bulletWorld.cxx) | `BulletWorld::do_physics()` |
| 粒子物理 | [`panda/src/physics/physicsManager.cxx`](panda/src/physics/physicsManager.cxx) | `PhysicsManager` |
| EGG 格式 | [`panda/src/egg/eggData.h`](panda/src/egg/eggData.h) | `EggData` |
| 应用框架 | [`direct/src/showbase/ShowBase.py`](direct/src/showbase/ShowBase.py) | `ShowBase.__init__()` |
| 任务调度 | [`direct/src/task/Task.py`](direct/src/task/Task.py) | `TaskManager` |
| 状态机 | [`direct/src/fsm/FSM.py`](direct/src/fsm/FSM.py) | `FSM.request()` |
| 时间线动画 | [`direct/src/interval/Interval.py`](direct/src/interval/Interval.py) | `Interval.setT()` |
| 配置变量 | [`dtool/src/prc/configVariable.h`](dtool/src/prc/configVariable.h) | `ConfigVariable` |

### 15.2 算法复杂度分析

| 算法 | 时间复杂度 | 空间复杂度 | 备注 |
|------|-----------|-----------|------|
| 视锥体裁剪遍历 | O(n) 最坏，O(log n) 平均 | O(depth) | n=节点数，早期剔除子树 |
| RenderState 合成 | O(k) 均摊 | O(S) | k=属性数，S=缓存状态数 |
| Bullet 宽相（AABB树） | O(n log n) | O(n) | n=刚体数 |
| Bullet 宽相（SAP） | O(n + k) | O(n) | k=重叠对数 |
| 骨骼动画更新 | O(J × A) | O(J) | J=关节数，A=活跃动画数 |
| 碰撞检测（内置） | O(C × S) | O(C) | C=碰撞体数，S=场景节点数 |

### 15.3 延伸阅读

- **Panda3D 官方手册**: https://docs.panda3d.org/
- **Carnegie Mellon ETC 技术报告**: Panda3D 原始设计文档
- **Bullet Physics SDK 文档**: https://pybullet.org/
- **Real-Time Rendering (4th Ed.)**: 视锥体裁剪、状态排序等算法的理论基础
- **Game Engine Architecture (3rd Ed.)**: 场景图、任务系统、动画系统的通用设计模式

---

*本报告基于 Panda3D master 分支源码分析生成，覆盖引擎核心模块约 15 万行 C++ 代码和 5 万行 Python 代码。*