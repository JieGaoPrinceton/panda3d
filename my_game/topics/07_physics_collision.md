# 专题07：物理与碰撞检测

## 目录
1. [问题背景](#1-问题背景)
2. [数学原理](#2-数学原理)
3. [工程实践](#3-工程实践)
4. [Panda3D 源码剖析](#4-panda3d-源码剖析)
5. [代码演示](#5-代码演示)
6. [性能优化](#6-性能优化)
7. [小结](#小结)

---

## 1. 问题背景

碰撞检测是游戏引擎中最核心的子系统之一，需要回答：**两个物体是否相交？交叉深度和法线是什么？**

| 挑战 | 描述 |
|------|------|
| **精度 vs 性能** | 精确凸包碰撞代价高，简化形状（球、胶囊）快但不准确 |
| **穿透问题** | 高速物体在一帧内可能穿过薄墙（隧道效应） |
| **O(n²) 复杂度** | n 个物体两两检测需要 O(n²) 次测试 |
| **响应多样性** | 不同场景需要不同响应：推挤、事件触发、重力、流体 |
| **双分派问题** | 球-球、球-平面、射线-球等不同组合需要不同算法 |

Panda3D 的碰撞系统是**纯软件实现**的碰撞检测框架（不依赖 Bullet/ODE），专为游戏逻辑碰撞设计。

---

## 2. 数学原理

### 2.1 分离轴定理（SAT）

**定理**：两个凸多边形不相交，当且仅当存在一条轴，使得两个多边形在该轴上的投影不重叠。

对于 3D 凸多面体 A 和 B，需要测试的轴：
- A 的所有面法线（最多 m 条）
- B 的所有面法线（最多 n 条）
- A 的每条边与 B 的每条边的叉积（最多 m x n 条）

**投影重叠测试**：

设轴方向为单位向量 n，物体 A 在轴上的投影区间为 [a_min, a_max]，物体 B 为 [b_min, b_max]。

若 a_max < b_min 或 b_max < a_min，则存在分离轴，两物体不相交。

**穿透深度**（Penetration Depth）：

若所有轴都重叠，穿透深度为所有轴上重叠量的最小值，对应最小穿透深度的轴即为**碰撞法线**。

**SAT 的优势**：
- 早期退出（找到一条分离轴即可停止）
- 同时给出穿透深度和法线
- 适合 AABB、OBB、凸多边形

### 2.2 GJK 算法

GJK（Gilbert-Johnson-Keerthi）算法利用**闵可夫斯基差**（Minkowski Difference）判断两个凸体是否相交。

**闵可夫斯基差**：A ⊖ B = { a - b | a ∈ A, b ∈ B }

**关键性质**：A 和 B 相交 当且仅当 原点在 A ⊖ B 内部。

**支撑函数**（Support Function）：
S_{A⊖B}(d) = S_A(d) - S_B(-d)，其中 S_A(d) = argmax_{a∈A} (a·d) 是 A 在方向 d 上的最远点。

**GJK 迭代**：
1. 选择初始方向 d
2. 计算支撑点 p = S_{A⊖B}(d)
3. 若 p·d < 0，原点不在 A⊖B 内，不相交
4. 将 p 加入单纯形（simplex），更新 d 为指向原点的方向
5. 重复直到单纯形包含原点或确认不相交

**EPA 算法**（Expanding Polytope Algorithm）：在 GJK 确认相交后，用于计算穿透深度和碰撞法线。

### 2.3 基本几何相交测试

#### 球-球相交



#### 射线-球相交



#### 射线-平面相交



#### 球-平面相交



### 2.4 连续碰撞检测（CCD）

**问题**：离散碰撞检测在高速物体时会出现隧道效应（Tunneling）。

**Panda3D 的 CCD 方案**：

原理：将碰撞体从上一帧位置到当前帧位置扫掠（Sweep），检测扫掠体积与静态物体的相交。

对于球体，扫掠体积是一个**胶囊体**（Capsule）：
- 胶囊体 = 球心从 P_prev 到 P_curr 的线段 + 半径 r 的膨胀

**时间参数化**（TOI - Time of Impact）：
- t_impact = 使 |P(t) - C_wall| = r_sphere + r_wall 的最小 t ∈ [0, 1]

---

## 3. 工程实践

### 3.1 宽相 vs 窄相

碰撞检测分两个阶段：

**宽相（Broad Phase）**：快速排除明显不相交的物体对
- 使用 AABB（轴对齐包围盒）或 BVH（包围体层次）
- 时间复杂度：O(n log n) 或 O(n + k)，k 为候选对数量
- Panda3D 使用场景图的 BoundingVolume 层次作为宽相

**窄相（Narrow Phase）**：对候选对进行精确相交测试
- 使用具体形状（球、胶囊、多边形）的精确算法
- 时间复杂度：O(1) 每对（对于简单形状）
- Panda3D 的 CollisionSolid 子类实现各种精确测试

**Panda3D 的宽相实现**：



### 3.2 碰撞掩码系统

Panda3D 使用 32 位掩码（BitMask32）控制哪些物体之间可以发生碰撞：



**掩码语义**：
- ：该碰撞体能检测到哪些类型的物体
- ：该碰撞体能被哪些类型的物体检测到

### 3.3 双分派（Double Dispatch）模式

碰撞检测的核心问题：不同形状组合需要不同算法，但 C++ 只支持单分派（虚函数）。

**Panda3D 的解决方案**：两级虚函数调用



**示例**：射线 vs 球体

# 1 "<stdin>"
# 1 "<built-in>" 1
# 1 "<built-in>" 3
# 481 "<built-in>" 3
# 1 "<command line>" 1
# 1 "<built-in>" 2
# 1 "<stdin>" 2

**碰撞矩阵**（Panda3D 支持的组合）：

| From \ Into | Sphere | Box | Capsule | Plane | Polygon | FloorMesh |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Sphere** | O | O | O | O | O | O |
| **Ray** | O | O | O | O | O | O |
| **Segment** | O | O | O | O | O | O |
| **Box** | O | O | - | O | - | - |
| **Capsule** | O | O | - | O | - | - |
| **Parabola** | O | - | - | O | O | - |

### 3.4 碰撞响应策略

| Handler | 用途 | 原理 |
|---------|------|------|
| CollisionHandlerQueue | 收集所有碰撞信息 | 存储 CollisionEntry 列表 |
| CollisionHandlerEvent | 触发事件（进入/离开/持续） | 比较前后帧碰撞集合 |
| CollisionHandlerPusher | 推挤（防穿墙） | 沿法线方向移动 from 节点 |
| CollisionHandlerFluidPusher | 流体推挤（高速物体） | 结合 CCD 的推挤 |
| CollisionHandlerGravity | 重力 + 地面检测 | 向下射线 + 高度调整 |
| CollisionHandlerFloor | 地面吸附 | 向下射线，保持在地面上 |

---
## 4. Panda3D 源码剖析

### 4.1 CollisionTraverser 遍历器

**文件**：[`collisionTraverser.h`](panda/src/collide/collisionTraverser.h)

```cpp
// collisionTraverser.h:46
class EXPCL_PANDA_COLLIDE CollisionTraverser : public Namable {
public:
  // 注册碰撞发起者（from）和对应的处理器
  void add_collider(const NodePath &collider, CollisionHandler *handler);
  bool remove_collider(const NodePath &collider);

  // 核心：遍历场景图，执行所有碰撞检测
  BLOCKING void traverse(const NodePath &root);

  // CCD 支持：是否考虑上一帧的变换
  void set_respect_prev_transform(bool flag);
  bool get_respect_prev_transform() const;

  // 调试可视化
  void show_collisions(NodePath root);
  void hide_collisions();

private:
  // 内部：比较 from 碰撞体与场景中的 into 节点
  void compare_collider_to_node(CollisionEntry &entry,
      const GeometricBoundingVolume *from_node_gbv,
      const GeometricBoundingVolume *into_node_gbv);

  void compare_collider_to_geom_node(CollisionEntry &entry,
      const GeometricBoundingVolume *from_node_gbv,
      const GeometricBoundingVolume *into_node_gbv);

  // 存储所有注册的 (collider, handler) 对
  typedef pvector<ColliderDef> Colliders;
  Colliders _colliders;
};
```

**`traverse()` 的执行流程**：

```
traverse(root)
  对每个注册的 collider（from 节点）：
    获取 from 的 CollisionSolid 和 BoundingVolume
    递归遍历 root 场景图：
      宽相：from_bv 与 into_bv 相交测试
        不相交 -> 跳过整个子树（剪枝）
      窄相：对每个 CollisionNode 中的 CollisionSolid：
        检查 from_mask & into_mask
        调用 from_solid->test_intersection(entry)
  对每个碰撞结果，调用对应 handler->add_entry(entry)
```

### 4.2 CollisionSolid 碰撞体基类

**文件**：[`collisionSolid.h`](panda/src/collide/collisionSolid.h)

```cpp
// collisionSolid.h:45
class EXPCL_PANDA_COLLIDE CollisionSolid : public CopyOnWriteObject {
public:
  // 获取碰撞体的原点（用于宽相测试）
  virtual LPoint3 get_collision_origin() const = 0;

  // 切线/法线控制
  void set_tangible(bool tangible);           // 是否参与推挤响应
  bool is_tangible() const;

  // 有效法线（覆盖计算出的碰撞法线）
  void set_effective_normal(const LVector3 &effective_normal);
  bool has_effective_normal() const;
  bool get_respect_effective_normal() const;

  // 包围体（用于宽相）
  CPT(BoundingVolume) get_bounds() const;
  void set_bounds(const BoundingVolume *bounding_volume);

protected:
  // 子类实现：计算内部包围体
  virtual PT(BoundingVolume) compute_internal_bounds() const;

  // 核心：执行相交测试（双分派第一级）
  virtual PT(CollisionEntry) test_intersection(
      const CollisionEntry &entry) const;

  // 双分派第二级：各 from 形状调用对应的 into 方法
  virtual PT(CollisionEntry) test_intersection_from_sphere(
      const CollisionEntry &entry) const;
  virtual PT(CollisionEntry) test_intersection_from_ray(
      const CollisionEntry &entry) const;
  virtual PT(CollisionEntry) test_intersection_from_segment(
      const CollisionEntry &entry) const;
  virtual PT(CollisionEntry) test_intersection_from_box(
      const CollisionEntry &entry) const;
  virtual PT(CollisionEntry) test_intersection_from_capsule(
      const CollisionEntry &entry) const;

  // 标志位
  enum Flags {
    F_tangible              = 0x01,  // 参与推挤
    F_effective_normal      = 0x02,  // 使用自定义法线
    F_viz_geom_stale        = 0x04,  // 可视化几何体需要更新
    F_viz_bounds_stale      = 0x08,
    F_internal_bounds_stale = 0x10,
  };
  unsigned int _flags;
};
```

**`effective_normal` 的用途**：

对于斜坡地面，碰撞法线可能是斜的，导致角色被推向侧面。设置 `effective_normal = (0,0,1)` 可以让推挤响应始终沿垂直方向，实现平滑的斜坡行走。

### 4.3 碰撞体类型层次

```
CollisionSolid（抽象基类）
├── CollisionSphere          球体（最快，推荐用于角色）
├── CollisionBox             轴对齐盒子
├── CollisionCapsule         胶囊体（球+圆柱，适合角色）
├── CollisionInvSphere       反向球（内部碰撞，如天空盒）
├── CollisionPlane           无限平面
├── CollisionPolygon         任意多边形（精确但慢）
├── CollisionGeom            几何体碰撞（最精确，最慢）
├── CollisionFloorMesh       地面网格（优化的地面检测）
├── CollisionHeightfield     高度图地形
├── CollisionRay             射线（无限长，单向）
├── CollisionSegment         线段（有限长）
├── CollisionLine            直线（无限长，双向）
└── CollisionParabola        抛物线（投射物轨迹）
```

**各形状性能对比**：

| 形状 | 相交测试速度 | 精确度 | 推荐用途 |
|------|------------|--------|---------|
| Sphere | 极快 | 低 | 角色、子弹、拾取物 |
| Capsule | 快 | 中 | 角色控制器 |
| Box | 快 | 中 | 箱子、建筑 |
| Ray/Segment | 极快 | 高 | 射线拾取、地面检测 |
| Plane | 极快 | 高 | 地面、墙壁（无限） |
| Polygon | 中 | 高 | 精确地形 |
| FloorMesh | 中 | 高 | 复杂地面 |
| Geom | 慢 | 最高 | 精确碰撞（慎用） |

### 4.4 CollisionHandler 响应处理器

**CollisionHandlerEvent**（事件触发）：

```cpp
// 三种事件模式
handler->add_in_pattern("enter-%in");    // 进入时触发
handler->add_again_pattern("stay-%in");  // 持续接触时触发
handler->add_out_pattern("exit-%in");    // 离开时触发

// %in 会被替换为 into 节点的名称
// %fn 会被替换为 from 节点的名称
```

**CollisionHandlerPusher**（推挤）：

推挤算法：
1. 获取碰撞法线 n 和穿透深度 d
2. 将 from 节点沿 n 方向移动 d 距离
3. 若有多个碰撞，累加所有推挤向量

```cpp
// 内部实现伪代码
void CollisionHandlerPusher::handle_entries() {
  for (auto &entry : _entries) {
    LVector3 normal = entry->get_surface_normal();
    // 计算推挤向量
    LVector3 push = normal * penetration_depth;
    // 移动 from 节点
    from_node.set_pos(from_node.get_pos() + push);
  }
}
```

---

## 5. 代码演示

### 5.1 Python：基本碰撞设置

```python
from panda3d.core import (
    CollisionTraverser, CollisionNode, CollisionSphere,
    CollisionHandlerQueue, BitMask32
)

class CollisionDemo:
    def __init__(self, base):
        self.base = base
        # 1. 创建碰撞遍历器
        self.cTrav = CollisionTraverser('main_traverser')
        # 2. 创建碰撞处理器（收集碰撞信息）
        self.cQueue = CollisionHandlerQueue()

        # 3. 为玩家创建碰撞体（from 节点）
        player_col_node = CollisionNode('player_collider')
        player_col_node.add_solid(CollisionSphere(0, 0, 0, 0.5))
        player_col_node.set_from_collide_mask(BitMask32.bit(0))
        player_col_node.set_into_collide_mask(BitMask32.all_off())
        player_col_np = base.player.attach_new_node(player_col_node)

        # 4. 注册到遍历器
        self.cTrav.add_collider(player_col_np, self.cQueue)

        # 5. 为场景物体创建碰撞体（into 节点）
        wall_col_node = CollisionNode('wall_collider')
        wall_col_node.add_solid(CollisionSphere(0, 0, 0, 1.0))
        wall_col_node.set_from_collide_mask(BitMask32.all_off())
        wall_col_node.set_into_collide_mask(BitMask32.bit(0))
        base.wall.attach_new_node(wall_col_node)

        # 6. 在游戏循环中执行碰撞检测
        base.taskMgr.add(self.collision_task, 'collision_task')

    def collision_task(self, task):
        self.cTrav.traverse(self.base.render)
        for i in range(self.cQueue.get_num_entries()):
            entry = self.cQueue.get_entry(i)
            into_np = entry.get_into_node_path()
            print(f"碰撞：{entry.get_from_node().get_name()} -> {entry.get_into_node().get_name()}")
            print(f"  碰撞点：{entry.get_surface_point(into_np)}")
            print(f"  碰撞法线：{entry.get_surface_normal(into_np)}")
        self.cQueue.clear_entries()
        return task.cont
```

### 5.2 Python：碰撞掩码过滤

```python
from panda3d.core import BitMask32, CollisionNode, CollisionSphere

# 定义碰撞层
class CollisionLayers:
    GROUND   = BitMask32.bit(0)
    WALL     = BitMask32.bit(1)
    ENEMY    = BitMask32.bit(2)
    PLAYER   = BitMask32.bit(3)
    TRIGGER  = BitMask32.bit(4)
    BULLET   = BitMask32.bit(5)

def setup_player_collision(player_np):
    col_node = CollisionNode('player')
    col_node.add_solid(CollisionSphere(0, 0, 0.9, 0.4))  # 身体球
    col_node.add_solid(CollisionSphere(0, 0, 0.3, 0.4))  # 脚部球
    # 玩家检测：地面、墙壁、敌人、触发器
    col_node.set_from_collide_mask(
        CollisionLayers.GROUND | CollisionLayers.WALL |
        CollisionLayers.ENEMY  | CollisionLayers.TRIGGER
    )
    # 玩家被：子弹检测到
    col_node.set_into_collide_mask(CollisionLayers.PLAYER)
    return player_np.attach_new_node(col_node)

def setup_bullet_collision(bullet_np):
    col_node = CollisionNode('bullet')
    col_node.add_solid(CollisionSphere(0, 0, 0, 0.1))
    col_node.set_from_collide_mask(
        CollisionLayers.PLAYER | CollisionLayers.ENEMY | CollisionLayers.WALL
    )
    col_node.set_into_collide_mask(CollisionLayers.BULLET)
    return bullet_np.attach_new_node(col_node)

def setup_trigger(trigger_np):
    col_node = CollisionNode('trigger_zone')
    col_node.add_solid(CollisionSphere(0, 0, 0, 3.0))
    col_node.set_from_collide_mask(BitMask32.all_off())
    col_node.set_into_collide_mask(CollisionLayers.PLAYER)
    return trigger_np.attach_new_node(col_node)
```

### 5.3 Python：自定义碰撞响应（事件系统）

```python
from panda3d.core import (
    CollisionTraverser, CollisionNode, CollisionSphere,
    CollisionHandlerEvent, BitMask32
)

class EventCollisionSystem:
    def __init__(self, base):
        self.base = base
        self.cTrav = CollisionTraverser()
        self.cEvent = CollisionHandlerEvent()

        # 设置事件模式：%in = into节点名，%fn = from节点名
        self.cEvent.add_in_pattern('%fn-enter-%in')    # 进入时
        self.cEvent.add_again_pattern('%fn-stay-%in')  # 持续时
        self.cEvent.add_out_pattern('%fn-exit-%in')    # 离开时

        # 注册玩家碰撞体
        player_col = CollisionNode('player')
        player_col.add_solid(CollisionSphere(0, 0, 0, 0.5))
        player_col.set_from_collide_mask(BitMask32.bit(0))
        player_col_np = base.player.attach_new_node(player_col)
        self.cTrav.add_collider(player_col_np, self.cEvent)

        # 注册触发器碰撞体
        trigger_col = CollisionNode('treasure_trigger')
        trigger_col.add_solid(CollisionSphere(0, 0, 0, 2.0))
        trigger_col.set_into_collide_mask(BitMask32.bit(0))
        base.treasure.attach_new_node(trigger_col)

        # 监听碰撞事件
        base.accept('player-enter-treasure_trigger', self.on_enter_treasure)
        base.accept('player-stay-treasure_trigger',  self.on_stay_treasure)
        base.accept('player-exit-treasure_trigger',  self.on_exit_treasure)
        base.taskMgr.add(self.update, 'collision_update')

    def on_enter_treasure(self, entry):
        print("进入宝藏区域！")

    def on_stay_treasure(self, entry):
        pass

    def on_exit_treasure(self, entry):
        print("离开宝藏区域")

    def update(self, task):
        self.cTrav.traverse(self.base.render)
        return task.cont
```

### 5.4 Python：角色控制器（推挤+重力）

```python
from panda3d.core import (
    CollisionTraverser, CollisionNode,
    CollisionSphere, CollisionRay,
    CollisionHandlerPusher, CollisionHandlerGravity,
    BitMask32, Vec3
)

class CharacterController:
    def __init__(self, base, character_np):
        self.base = base
        self.char = character_np
        self.cTrav = CollisionTraverser()

        # ── 推挤处理器（防止穿墙）────────────────────────────────────────────
        self.pusher = CollisionHandlerPusher()
        self.pusher.set_horizontal(True)  # 只在水平方向推挤

        body_col = CollisionNode('char_body')
        body_col.add_solid(CollisionSphere(0, 0, 0.5, 0.4))  # 腰部
        body_col.add_solid(CollisionSphere(0, 0, 1.2, 0.4))  # 胸部
        body_col.set_from_collide_mask(BitMask32.bit(1))      # 检测墙壁层
        body_col.set_into_collide_mask(BitMask32.all_off())
        body_col_np = character_np.attach_new_node(body_col)

        self.cTrav.add_collider(body_col_np, self.pusher)
        self.pusher.add_collider(body_col_np, character_np)

        # ── 重力处理器（地面检测）────────────────────────────────────────────
        self.gravity = CollisionHandlerGravity()
        self.gravity.set_gravity(9.8)
        self.gravity.set_max_slope(45.0)
        self.gravity.set_reach(0.1)

        floor_ray = CollisionNode('char_floor_ray')
        floor_ray.add_solid(CollisionRay(0, 0, 0.5, 0, 0, -1))  # 从腰部向下
        floor_ray.set_from_collide_mask(BitMask32.bit(0))
        floor_ray.set_into_collide_mask(BitMask32.all_off())
        floor_ray_np = character_np.attach_new_node(floor_ray)

        self.cTrav.add_collider(floor_ray_np, self.gravity)
        self.gravity.add_collider(floor_ray_np, character_np)

        # ── CCD：防止高速穿透 ─────────────────────────────────────────────────
        self.cTrav.set_respect_prev_transform(True)
        base.taskMgr.add(self.update, 'char_collision')

    def update(self, task):
        self.cTrav.traverse(self.base.render)
        return task.cont

    def jump(self):
        # 触发跳跃：设置初始向上速度
        self.gravity.set_velocity(Vec3(0, 0, 5.0))
```

### 5.5 Python：射线拾取（Ray Picking）

```python
from panda3d.core import (
    CollisionTraverser, CollisionNode, CollisionRay,
    CollisionHandlerQueue, BitMask32
)

class RayPicker:
    def __init__(self, base):
        self.base = base
        self.cTrav = CollisionTraverser()
        self.cQueue = CollisionHandlerQueue()

        self.pick_ray = CollisionRay()
        pick_node = CollisionNode('mouse_ray')
        pick_node.add_solid(self.pick_ray)
        pick_node.set_from_collide_mask(BitMask32.bit(0))
        pick_node.set_into_collide_mask(BitMask32.all_off())

        pick_np = base.camera.attach_new_node(pick_node)
        self.cTrav.add_collider(pick_np, self.cQueue)
        base.accept('mouse1', self.on_click)

    def on_click(self):
        # 鼠标点击时执行射线拾取
        if not self.base.mouseWatcherNode.has_mouse():
            return
        mouse_pos = self.base.mouseWatcherNode.get_mouse()
        # 设置射线从相机出发，穿过鼠标位置
        self.pick_ray.set_from_lens(
            self.base.camNode,
            mouse_pos.get_x(),
            mouse_pos.get_y()
        )
        self.cTrav.traverse(self.base.render)
        if self.cQueue.get_num_entries() > 0:
            self.cQueue.sort_entries()
            entry = self.cQueue.get_entry(0)
            picked_np = entry.get_into_node_path()
            hit_point = entry.get_surface_point(self.base.render)
            print(f"点击了：{picked_np.get_name()}")
            print(f"点击位置：{hit_point}")
            return picked_np, hit_point
        return None, None
```

---

## 6. 性能优化

### 6.1 碰撞体选择原则

```python
# 错误：对复杂模型使用 CollisionGeom（极慢，每帧测试所有三角形）
# col_node.add_solid(CollisionGeom(model.node()))

# 正确：用简化形状近似
from panda3d.core import CollisionCapsule, CollisionBox, Point3

# 角色用胶囊体
col_node.add_solid(CollisionCapsule(0, 0, 0.2, 0, 0, 1.6, 0.4))

# 建筑用多个盒子组合
col_node.add_solid(CollisionBox(Point3(-1, -1, 0), Point3(1, 1, 2)))
```

### 6.2 碰撞掩码优化

```python
# 错误：所有物体使用默认掩码（全部互相检测）
col_node.set_from_collide_mask(BitMask32.all_on())
col_node.set_into_collide_mask(BitMask32.all_on())

# 正确：精确设置掩码，减少不必要的测试
col_node.set_from_collide_mask(BitMask32.bit(0) | BitMask32.bit(1))
col_node.set_into_collide_mask(BitMask32.bit(2))
```

### 6.3 减少碰撞体数量

```python
# 错误：每个小物体都有独立碰撞体（1000个碰撞体，O(n^2) 测试）
# for i in range(1000):
#     coin = loader.load_model('coin')
#     col = CollisionNode('coin_col')
#     col.add_solid(CollisionSphere(0, 0, 0, 0.2))
#     coin.attach_new_node(col)

# 正确：使用触发区域代替单个碰撞体
# 用一个大的触发区域检测玩家是否靠近，再精确检测
trigger = CollisionNode('coins_area')
trigger.add_solid(CollisionSphere(0, 0, 0, 5.0))  # 5米范围内才精确检测
```

### 6.4 碰撞遍历器分离

```python
# 不同用途使用不同遍历器，避免不必要的交叉检测
cTrav_physics  = CollisionTraverser('physics')   # 物理碰撞（每帧）
cTrav_picking  = CollisionTraverser('picking')   # 鼠标拾取（按需）
cTrav_triggers = CollisionTraverser('triggers')  # 触发器（每帧，但物体少）

# 拾取遍历器只在点击时运行，不加入 taskMgr
```

### 6.5 性能对比

| 场景 | 碰撞体类型 | 每帧时间（100物体） |
|------|-----------|-------------------|
| 全部 CollisionGeom | 精确网格 | ~50ms（不可接受） |
| 全部 CollisionSphere | 球体 | ~0.5ms |
| 混合（球+胶囊+盒子） | 简化形状 | ~1ms |
| 启用 CCD | 球体+扫掠 | ~2ms |

---

## 小结

| 知识点 | 核心要点 |
|--------|---------|
| **SAT** | 找到分离轴即可判断不相交；穿透深度 = 最小重叠量 |
| **GJK** | 闵可夫斯基差 + 支撑函数；原点在差集内 = 相交 |
| **宽相/窄相** | BVH 宽相剪枝 + 精确形状窄相；两阶段大幅降低复杂度 |
| **双分派** | 两级虚函数解决 N×M 形状组合问题 |
| **碰撞掩码** | 32位掩码精确控制碰撞对；from & into != 0 才检测 |
| **CCD** | set_respect_prev_transform(True) 防隧道效应 |
| **effective_normal** | 斜坡行走的关键：覆盖碰撞法线为垂直方向 |
| **Handler 选择** | Queue=调试，Event=触发器，Pusher=防穿墙，Gravity=角色 |

**Panda3D 碰撞系统的设计哲学**：
- 简单优先：优先使用球体、胶囊等简单形状
- 分层设计：掩码系统实现精确的碰撞过滤
- 软件实现：不依赖物理引擎，轻量但功能完整
- 可扩展：通过继承 CollisionSolid 可添加自定义形状
