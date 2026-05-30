# 专题02：场景图与空间加速结构

## 目录
1. [问题背景](#1-问题背景)
2. [数学原理](#2-数学原理)
   - 2.1 树形场景图的代数结构
   - 2.2 包围体层次（BVH）理论
   - 2.3 视锥体裁剪的几何数学
   - 2.4 空间查询的复杂度分析
3. [工程实践](#3-工程实践)
   - 3.1 脏标记（Dirty Flag）传播
   - 3.2 懒惰求值（Lazy Evaluation）
   - 3.3 DrawMask 位掩码系统
   - 3.4 Portal 遮挡剔除
4. [Panda3D 源码解析](#4-panda3d-源码解析)
   - 4.1 PandaNode 包围体系统
   - 4.2 update_cached() 递归更新
   - 4.3 CullTraverserData 视锥变换
5. [代码演示](#5-代码演示)
6. [性能分析](#6-性能分析)

---

## 1. 问题背景

3D 场景中可能有数万个物体，每帧都对所有物体调用 GPU 绘制命令是不可接受的。场景图（Scene Graph）解决两个核心问题：

1. **层次变换**：子节点自动继承父节点的位置/旋转/缩放，无需手动计算世界坐标
2. **空间剔除**：利用层次包围体，快速排除不在视野内的整个子树，避免无效绘制

```
场景图示例：
         Root
        /    \
    City      Sky
   /    \       \
 Bldg1  Bldg2   Sun
 /  \
L1   L2
```

当 `City` 节点的包围球不与视锥体相交时，`Bldg1`、`Bldg2` 及其所有子节点都被一次性剔除，无需逐一检测。

---

## 2. 数学原理

### 2.1 树形场景图的代数结构

场景图是一棵有向无环图（DAG），节点 $n$ 的**世界变换矩阵**定义为从根到该节点路径上所有局部变换的复合：

$$M_{world}(n) = M_{local}(n_0) \cdot M_{local}(n_1) \cdots M_{local}(n)$$

其中 $n_0, n_1, \ldots, n$ 是从根到 $n$ 的路径。

**关键性质**：
- 矩阵乘法满足结合律：$(A \cdot B) \cdot C = A \cdot (B \cdot C)$
- 但不满足交换律：$A \cdot B \neq B \cdot A$（旋转顺序敏感）

**增量更新**：若节点 $n$ 的局部变换改变，只需重新计算 $n$ 及其所有后代的世界变换，而非整棵树。

### 2.2 包围体层次（BVH）理论

**包围体（Bounding Volume, BV）** 是包含几何体的简单形状，用于快速相交测试。

常见类型及其权衡：

| 类型 | 存储 | 相交测试 | 紧密度 |
|------|------|----------|--------|
| 包围球（Sphere） | 4 floats | O(1) | 低 |
| AABB（轴对齐包围盒） | 6 floats | O(1) | 中 |
| OBB（有向包围盒） | 15 floats | O(n) | 高 |
| k-DOP | 2k floats | O(k) | 可调 |

**BVH 构建**：Panda3D 使用**自底向上**的方式构建 BVH：
- 叶节点：包含几何体的精确包围体
- 内部节点：所有子节点包围体的并集（`around()`）

**BVH 查询复杂度**：
- 最坏情况：$O(n)$（所有节点都在视野内）
- 平均情况：$O(\log n)$（大部分子树被早期剔除）
- 最优情况：$O(1)$（根节点即被剔除）

### 2.3 视锥体裁剪的几何数学

**视锥体（View Frustum）** 由 6 个平面定义：近平面、远平面、左、右、上、下。

每个平面用法向量 $\mathbf{n}$ 和距离 $d$ 表示：$\mathbf{n} \cdot \mathbf{x} + d = 0$

**球体-平面相交测试**：

给定球心 $\mathbf{c}$，半径 $r$，平面 $(\mathbf{n}, d)$：

$$\text{dist} = \mathbf{n} \cdot \mathbf{c} + d$$

- $\text{dist} > r$：球完全在平面外侧 → **剔除**
- $\text{dist} < -r$：球完全在平面内侧 → **完全包含**
- 否则：球与平面相交 → **部分包含，继续检测子节点**

**视锥变换到局部空间**：

Panda3D 的关键优化——不是将包围体变换到世界空间，而是将视锥体变换到节点的**局部空间**：

$$F_{local} = F_{world} \cdot M_{world}^{-1}$$

这样每个节点的包围体保持在其局部坐标系中，无需每帧重新计算。

### 2.4 空间查询的复杂度分析

设场景有 $N$ 个节点，树高为 $h$，每层平均分支因子为 $b$：

$$N = b^h \Rightarrow h = \log_b N$$

**视锥剔除效率**：
- 若视锥体覆盖场景的比例为 $p$，则期望访问节点数为 $O(p \cdot N + h)$
- 当 $p \ll 1$（如室内场景）时，效率极高

**包围体更新代价**：
- 单节点变换：需更新从该节点到根的路径，代价 $O(h) = O(\log N)$
- 使用脏标记延迟更新：实际代价摊销为 $O(1)$（仅在查询时才重算）

---

## 3. 工程实践

### 3.1 脏标记（Dirty Flag）传播

**问题**：每次节点变换都立即重算包围体代价高昂，且同一帧内可能多次修改。

**解决方案**：脏标记（Dirty Flag）模式

```
节点变换改变
    ↓
mark_bounds_stale()  ← 向上传播脏标记
    ↓
父节点也标记为脏
    ↓
... 直到根节点
    ↓
下一帧 CullTraverser 遍历时
    ↓
get_bounds() 检测到脏标记
    ↓
update_cached() 重新计算
```

**关键数据结构**（`pandaNode.cxx`）：
```cpp
UpdateSeq _last_update;        // 上次更新的序列号
UpdateSeq _next_update;        // 期望的最新序列号
UpdateSeq _last_bounds_update; // 上次包围体更新序列号
```

当 `_last_bounds_update != _next_update` 时，包围体被认为是脏的。

### 3.2 懒惰求值（Lazy Evaluation）

Panda3D 的包围体系统是**完全懒惰**的：
- 修改节点时只标记脏，不立即计算
- 只有在 `get_bounds()` 被调用时才触发重算
- 重算时递归检查子节点，若子节点也脏则先更新子节点

这种策略的优势：
1. 同一帧内多次修改只触发一次重算
2. 从未被查询的节点永远不会重算
3. 与多线程 Pipeline Cycler 天然兼容

### 3.3 DrawMask 位掩码系统

每个节点有两个 32 位掩码：

```cpp
DrawMask _draw_control_mask;  // 控制位：1 = 该位被此节点控制
DrawMask _draw_show_mask;     // 显示位：1 = 该位显示，0 = 隐藏
```

组合语义：

| control | show | 含义 |
|---------|------|------|
| 0 | 0 | 非渲染节点 |
| 0 | 1 | 正常可见 |
| 1 | 0 | 隐藏 |
| 1 | 1 | 强制显示（show-through） |

**向上传播规则**：父节点的净掩码是所有子节点掩码的并集，但有一个例外：若一个子节点隐藏（10）而另一个正常可见（01），结果为正常可见（01），因为只有**所有**渲染节点都隐藏时才向上传播隐藏状态。

### 3.4 Portal 遮挡剔除

对于室内场景，视锥剔除不够高效（大量物体在视锥内但被墙壁遮挡）。Portal 剔除通过"门洞"限制可见区域：

```
[房间A] --[门洞]--> [房间B]
```

遍历时，每经过一个 Portal，视锥体被裁剪为 Portal 开口的形状，从而排除门洞外的所有物体。

Panda3D 通过 `OccluderEffect` 和 `CullPlanes` 实现类似功能。

---

## 4. Panda3D 源码解析

### 4.1 PandaNode 包围体系统

**文件**：[`panda/src/pgraph/pandaNode.cxx`](../../panda/src/pgraph/pandaNode.cxx)

#### `get_bounds()` — 懒惰求值入口

```cpp
// pandaNode.cxx:1875
CPT(BoundingVolume) PandaNode::
get_bounds(Thread *current_thread) const {
  int pipeline_stage = current_thread->get_pipeline_stage();
  CDLockedStageReader cdata(_cycler, pipeline_stage, current_thread);

  // 检查脏标记：last_bounds_update != next_update 表示包围体已过期
  if (cdata->_last_bounds_update != cdata->_next_update) {
    // 缓存失效，需要重建
    CPT(BoundingVolume) result;
    {
      PStatTimer timer(_update_bounds_pcollector);
      // update_cached() 会递归更新整个子树
      CDStageWriter cdataw =
        ((PandaNode *)this)->update_cached(true, pipeline_stage, cdata);
      result = cdataw->_external_bounds;
    }
    return result;
  }
  // 缓存有效，直接返回
  return cdata->_external_bounds;
}
```

**关键点**：
- `CDLockedStageReader` 是线程安全的读锁
- `_last_bounds_update != _next_update` 是脏标记检测
- `update_cached(true, ...)` 的 `true` 参数表示同时更新包围体

#### `mark_bounds_stale()` — 脏标记向上传播

```cpp
// pandaNode.cxx:1964
void PandaNode::
mark_bounds_stale(Thread *current_thread) const {
  // 遍历当前及上游所有 pipeline stage
  OPEN_ITERATE_CURRENT_AND_UPSTREAM_NOLOCK(_cycler, current_thread) {
    mark_bounds_stale(pipeline_stage, current_thread);
  }
  CLOSE_ITERATE_CURRENT_AND_UPSTREAM_NOLOCK(_cycler);
}
```

`mark_bounds_stale(pipeline_stage, ...)` 的内部实现会：
1. 递增 `_next_update` 序列号（使 `_last_bounds_update != _next_update`）
2. 对每个父节点递归调用 `mark_bounds_stale()`

#### `compute_internal_bounds()` — 叶节点包围体

```cpp
// pandaNode.cxx:2249
void PandaNode::
compute_internal_bounds(CPT(BoundingVolume) &internal_bounds,
                        int &internal_vertices,
                        int pipeline_stage,
                        Thread *current_thread) const {
  // 基类默认返回空包围球
  // GeomNode 等子类会重写此方法，计算几何体的精确包围体
  internal_bounds = new BoundingSphere;
  internal_vertices = 0;
}
```

#### `compute_external_bounds()` — 合并子节点包围体

```cpp
// pandaNode.cxx:2263
void PandaNode::
compute_external_bounds(CPT(BoundingVolume) &external_bounds,
                        BoundingVolume::BoundsType btype,
                        const BoundingVolume **volumes, size_t num_volumes,
                        int pipeline_stage, Thread *current_thread) const {

  CPT(TransformState) transform = get_transform(current_thread);
  PT(GeometricBoundingVolume) gbv;

  // 根据类型选择包围体形状
  if (btype == BoundingVolume::BT_box) {
    gbv = new BoundingBox;
  }
  else if (btype == BoundingVolume::BT_sphere || !transform->is_identity()) {
    // 有变换时必须用球（球在变换下保持球形）
    gbv = new BoundingSphere;
  }
  else {
    // 若所有子节点都是 AABB 且无变换，结果也是 AABB
    bool all_box = true;
    for (size_t i = 0; i < num_volumes; ++i) {
      if (volumes[i]->as_bounding_box() == nullptr) {
        all_box = false;
      }
    }
    gbv = all_box ? (PT(GeometricBoundingVolume))new BoundingBox
                  : (PT(GeometricBoundingVolume))new BoundingSphere;
  }

  if (num_volumes > 0) {
    // around() 计算所有子包围体的最小外接包围体
    const BoundingVolume **child_begin = &volumes[0];
    const BoundingVolume **child_end = child_begin + num_volumes;
    ((BoundingVolume *)gbv)->around(child_begin, child_end);

    // 应用节点自身的变换
    if (!transform->is_identity()) {
      gbv->xform(transform->get_mat());
    }
  }

  external_bounds = gbv;
}
```

### 4.2 update_cached() 递归更新

```cpp
// pandaNode.cxx:3231
PandaNode::CDStageWriter PandaNode::
update_cached(bool update_bounds, int pipeline_stage,
              PandaNode::CDLockedStageReader &cdata) {
  do {
    UpdateSeq last_update = cdata->_last_update;
    UpdateSeq next_update = cdata->_next_update;

    // 收集子节点列表
    PT(Down) down;
    {
      CDStageWriter cdataw(_cycler, pipeline_stage, cdata);
      down = cdataw->modify_down();
    }

    int num_children = down->size();
    const BoundingVolume **child_volumes = nullptr;
    int child_volumes_i = 0;

    if (update_bounds) {
      // 分配栈上数组存放子包围体指针
      child_volumes = (const BoundingVolume **)
        alloca(sizeof(BoundingVolume *) * (num_children + 1));

      // 先获取自身内部包围体（叶节点几何体）
      CPT(BoundingVolume) internal_bounds =
        get_internal_bounds(pipeline_stage, current_thread);

      if (!internal_bounds->is_empty()) {
        child_volumes[child_volumes_i++] = internal_bounds;
      }
    }

    // 遍历所有子节点
    for (int i = 0; i < num_children; ++i) {
      PandaNode *child = (*down)[i].get_child();
      CDLockedStageReader child_cdata(child->_cycler, pipeline_stage, current_thread);

      // 若子节点也是脏的，先递归更新子节点
      if (child_cdata->_last_bounds_update != child_cdata->_next_update) {
        CDStageWriter child_cdataw =
          child->update_cached(update_bounds, pipeline_stage, child_cdata);

        // 收集子节点的包围体
        if (update_bounds && !child_cdataw->_external_bounds->is_empty()) {
          child_volumes[child_volumes_i++] = child_cdataw->_external_bounds;
        }
      }
    }

    // 计算本节点的外部包围体（包含自身 + 所有子节点）
    if (update_bounds) {
      CPT(BoundingVolume) external_bounds;
      compute_external_bounds(external_bounds, btype,
                              child_volumes, child_volumes_i,
                              pipeline_stage, current_thread);
      cdataw->_external_bounds = external_bounds;
      cdataw->_last_bounds_update = next_update;  // 清除脏标记
    }

  } while (...); // 处理并发竞争的重试逻辑
}
```

**递归结构**：
```
update_cached(Root)
├── update_cached(City)        ← 若 City 是脏的
│   ├── update_cached(Bldg1)   ← 若 Bldg1 是脏的
│   │   ├── get_internal_bounds(L1)
│   │   └── get_internal_bounds(L2)
│   │   └── compute_external_bounds([L1_bv, L2_bv])
│   └── get_bounds(Bldg2)      ← 若 Bldg2 不脏，直接返回缓存
│   └── compute_external_bounds([Bldg1_bv, Bldg2_bv])
└── get_bounds(Sky)            ← 若 Sky 不脏，直接返回缓存
└── compute_external_bounds([City_bv, Sky_bv])
```

### 4.3 CullTraverserData 视锥变换

**文件**：[`panda/src/pgraph/cullTraverserData.cxx`](../../panda/src/pgraph/cullTraverserData.cxx)

#### `apply_transform()` — 将视锥变换到局部空间

```cpp
// cullTraverserData.cxx:96
void CullTraverserData::
apply_transform(const TransformState *node_transform) {
  if (!node_transform->is_identity()) {
    // 处理实例化（GPU Instancing）的特殊情况
    if (_instances != nullptr) {
      InstanceList *instances = new InstanceList(*_instances);
      for (InstanceList::Instance &instance : *instances) {
        instance.set_transform(
          instance.get_transform()->compose(node_transform));
      }
      _instances = std::move(instances);
      return;
    }

    // 累积世界变换：net_transform = parent_net_transform * node_local_transform
    _net_transform = _net_transform->compose(node_transform);

    if (_view_frustum != nullptr || _cull_planes != nullptr) {
      // 关键优化：将视锥体变换到节点的局部空间
      // 而不是将包围体变换到世界空间
      const LMatrix4 *inverse_mat = node_transform->get_inverse_mat();

      if (inverse_mat != nullptr) {
        if (_view_frustum != nullptr) {
          // 复制视锥体（避免修改父节点的视锥体）
          _view_frustum = _view_frustum->make_copy()
                            ->as_geometric_bounding_volume();

          // 用逆矩阵将视锥体变换到局部空间
          // F_local = F_world * M_world_to_local
          _view_frustum->xform(*inverse_mat);
        }

        if (_cull_planes != nullptr) {
          _cull_planes = _cull_planes->xform(*inverse_mat);
        }
      }
      else {
        // 奇异矩阵（如零缩放），无法求逆
        // 放弃视锥剔除，保守地认为所有子节点都可见
        pgraph_cat.warning()
          << "Singular transformation detected on node: "
          << get_node_path() << "\n";
        _view_frustum = nullptr;
        _cull_planes = nullptr;
      }
    }
  }
}
```

#### `apply_transform_and_state()` — 完整的节点处理

```cpp
// cullTraverserData.cxx:31
void CullTraverserData::
apply_transform_and_state(CullTraverser *trav) {
  CPT(RenderState) node_state = _node_reader.get_state();

  // 处理 Camera Tag State（相机特定的状态覆盖）
  if (trav->has_tag_state_key() &&
      _node_reader.has_tag(trav->get_tag_state_key())) {
    const Camera *camera = trav->get_scene()->get_camera_node();
    std::string tag_state = _node_reader.get_tag(trav->get_tag_state_key());
    node_state = node_state->compose(camera->get_tag_state(tag_state));
  }

  // 更新 DrawMask
  _node_reader.compose_draw_mask(_draw_mask);

  // 处理 RenderEffects（Billboard、Compass 等特殊效果）
  const RenderEffects *node_effects = _node_reader.get_effects();
  if (!node_effects->has_cull_callback()) {
    apply_transform(_node_reader.get_transform());
  } else {
    // Billboard 等效果可能修改变换
    CPT(TransformState) node_transform = _node_reader.get_transform();
    node_effects->cull_callback(trav, *this, node_transform, node_state);
    apply_transform(node_transform);
    _node_reader.check_cached(false);
  }

  // 累积渲染状态
  if (!node_state->is_empty()) {
    _state = _state->compose(node_state);
  }

  // 处理裁剪平面（Clip Planes）
  if (clip_plane_cull) {
    const ClipPlaneAttrib *cpa = (const ClipPlaneAttrib *)
      node_state->get_attrib(ClipPlaneAttrib::get_class_slot());
    // ...
  }

  // 处理雾效（Fog）
  const FogAttrib *fog_attr;
  if (node_state->get_attrib(fog_attr)) {
    Fog *fog = fog_attr->get_fog();
    if (fog != nullptr) {
      fog->adjust_to_camera(trav->get_camera_transform());
    }
  }
}
```

---

## 5. 代码演示

### 5.1 Python：场景图基本操作

```python
from panda3d.core import NodePath, PandaNode, GeomNode, BoundingSphere, Point3

# ── 构建场景图 ──────────────────────────────────────────────────────────────
root = NodePath("root")
city = root.attach_new_node("city")
bldg1 = city.attach_new_node("building_1")
bldg2 = city.attach_new_node("building_2")

# 设置局部变换
city.set_pos(100, 0, 0)
bldg1.set_pos(0, 0, 0)   # 相对于 city
bldg2.set_pos(50, 0, 0)  # 相对于 city

# 获取世界坐标（自动计算 net_transform）
print(bldg1.get_pos(render))  # (100, 0, 0) — city + bldg1 的累积
print(bldg2.get_pos(render))  # (150, 0, 0)

# ── 包围体操作 ──────────────────────────────────────────────────────────────
# 获取节点的包围体（懒惰计算）
bounds = city.node().get_bounds()
print(f"City bounds: {bounds}")  # BoundingSphere 或 BoundingBox

# 手动设置自定义包围体（覆盖自动计算）
custom_sphere = BoundingSphere(Point3(0, 0, 5), 20.0)
bldg1.node().set_bounds(custom_sphere)
bldg1.node().set_final(True)  # 不再向下递归计算子节点包围体

# 强制重新计算包围体
bldg1.node().mark_bounds_stale()

# ── 可见性控制 ──────────────────────────────────────────────────────────────
# 隐藏节点（设置 DrawMask）
bldg2.hide()
bldg2.show()

# 按相机掩码控制可见性
from panda3d.core import BitMask32
MAIN_CAM_MASK = BitMask32.bit(0)
SHADOW_CAM_MASK = BitMask32.bit(1)

bldg1.show(MAIN_CAM_MASK)    # 主相机可见
bldg1.hide(SHADOW_CAM_MASK)  # 阴影相机不可见（不投射阴影）
```

### 5.2 Python：空间查询

```python
from panda3d.core import NodePath, CollisionTraverser, CollisionNode
from panda3d.core import CollisionSphere, CollisionHandlerQueue, Point3

# ── 射线拾取（Ray Picking）──────────────────────────────────────────────────
from panda3d.core import CollisionRay, CollisionHandlerQueue

picker = CollisionTraverser("picker")
pick_queue = CollisionHandlerQueue()

pick_node = CollisionNode("mouse_ray")
pick_node.set_from_collide_mask(GeomNode.get_default_collide_mask())
pick_ray = CollisionRay()
pick_node.add_solid(pick_ray)

pick_np = base.camera.attach_new_node(pick_node)
picker.add_collider(pick_np, pick_queue)

def pick_object(mouse_x, mouse_y):
    # 从鼠标位置发射射线
    pick_ray.set_from_lens(base.camNode, mouse_x, mouse_y)
    picker.traverse(render)

    if pick_queue.get_num_entries() > 0:
        pick_queue.sort_entries()
        hit = pick_queue.get_entry(0)
        return hit.get_into_node_path()
    return None

# ── 范围查询（Sphere Query）────────────────────────────────────────────────
def find_nodes_in_sphere(center: Point3, radius: float, root: NodePath):
    """查找在球形范围内的所有节点"""
    results = []
    query_sphere = BoundingSphere(center, radius)

    def check_node(np: NodePath):
        bounds = np.node().get_bounds()
        if bounds.contains(query_sphere) != BoundingVolume.IF_no_intersection:
            results.append(np)
            for child in np.get_children():
                check_node(child)

    check_node(root)
    return results
```

### 5.3 Python：LOD 节点（空间加速的应用）

```python
from panda3d.core import LODNode, NodePath

# LODNode 根据距离自动切换细节级别
lod = LODNode("my_lod")
lod_np = NodePath(lod)
lod_np.reparent_to(render)

# 加载不同精度的模型
high_detail = loader.load_model("building_high.egg")
med_detail = loader.load_model("building_med.egg")
low_detail = loader.load_model("building_low.egg")
billboard = loader.load_model("building_billboard.egg")

# 添加 LOD 级别：(switch_in_distance, switch_out_distance)
lod.add_switch(100, 0)    # 0-100 单位：高精度
lod.add_switch(300, 100)  # 100-300 单位：中精度
lod.add_switch(800, 300)  # 300-800 单位：低精度
lod.add_switch(2000, 800) # 800-2000 单位：广告牌

high_detail.reparent_to(lod_np)
med_detail.reparent_to(lod_np)
low_detail.reparent_to(lod_np)
billboard.reparent_to(lod_np)
```

### 5.4 Python：自定义包围体优化剔除

```python
from panda3d.core import BoundingBox, Point3

# 对于建筑物（轴对齐长方体），AABB 比球体更紧密
building_np = loader.load_model("skyscraper.egg")

# 手动设置精确的 AABB
tight_box = BoundingBox(
    Point3(-10, -10, 0),   # 最小角
    Point3(10, 10, 100)    # 最大角（100 单位高）
)
building_np.node().set_bounds(tight_box)

# 对于复杂不规则形状，用多个子节点分别设置包围体
complex_obj = NodePath("complex")
part1 = complex_obj.attach_new_node("part1")
part2 = complex_obj.attach_new_node("part2")
# part1 和 part2 各自有紧密的包围体
# complex_obj 的包围体自动合并两者
```

### 5.5 C++：自定义节点重写包围体计算

```cpp
// 自定义节点，重写 compute_internal_bounds()
class ProceduralTerrainNode : public PandaNode {
public:
  ProceduralTerrainNode(const std::string &name)
    : PandaNode(name), _width(1000.f), _height(1000.f), _max_elev(200.f) {}

  virtual void compute_internal_bounds(
      CPT(BoundingVolume) &internal_bounds,
      int &internal_vertices,
      int pipeline_stage,
      Thread *current_thread) const override {

    // 地形天然适合 AABB
    internal_bounds = new BoundingBox(
      LPoint3(-_width/2, -_height/2, 0),
      LPoint3(_width/2,  _height/2,  _max_elev)
    );
    internal_vertices = (int)(_width/10) * (int)(_height/10);
  }

  void set_max_elevation(float elev) {
    _max_elev = elev;
    mark_internal_bounds_stale();  // 触发重新计算
  }

private:
  float _width, _height, _max_elev;
};
```

---

## 6. 性能分析

### 6.1 包围体类型选择

| 场景类型 | 推荐包围体 | 原因 |
|----------|-----------|------|
| 角色/生物 | BoundingSphere | 旋转不变，更新代价低 |
| 建筑/家具 | BoundingBox | 轴对齐，更紧密 |
| 地形 | BoundingBox | 天然轴对齐 |
| 粒子系统 | BoundingSphere | 动态更新频繁，球更快 |

### 6.2 场景图深度 vs 宽度

| 结构 | 优点 | 缺点 |
|------|------|------|
| 深树（深度大） | 剔除粒度细 | 遍历开销大，缓存不友好 |
| 宽树（宽度大） | 遍历快 | 剔除效率低（大包围体） |
| 平衡树 | 最优剔除效率 | 需要手动组织 |

**实践建议**：
- 将空间上相邻的物体组织在同一父节点下
- 避免将相距很远的物体放在同一父节点（导致包围体过大）
- 深度控制在 5-10 层为宜

### 6.3 常见性能陷阱

```python
# ❌ 错误：将整个城市放在一个节点下
city = NodePath("city")
for i in range(10000):
    building = loader.load_model("building.egg")
    building.reparent_to(city)  # 所有建筑共享一个父节点
# 问题：city 的包围体包含所有建筑，视锥剔除几乎无效

# ✅ 正确：按区域分组
city = NodePath("city")
for block_x in range(10):
    for block_y in range(10):
        block = city.attach_new_node(f"block_{block_x}_{block_y}")
        block.set_pos(block_x * 100, block_y * 100, 0)
        for i in range(100):
            building = loader.load_model("building.egg")
            building.reparent_to(block)
# 优势：每个 block 有紧密的包围体，可以整块剔除

# ❌ 错误：频繁调用 get_bounds() 触发重算
for node in all_nodes:
    node.set_pos(new_pos[node])
    bounds = node.get_bounds()  # 每次 set_pos 后立即查询，触发重算

# ✅ 正确：批量修改后统一查询
for node in all_nodes:
    node.set_pos(new_pos[node])  # 只标记脏，不重算
# 统一查询（此时才触发一次批量重算）
for node in all_nodes:
    bounds = node.get_bounds()
```

---

## 小结

| 概念 | 核心思想 | Panda3D 实现 |
|------|----------|-------------|
| 场景图 | 层次变换，子节点继承父节点 | `NodePath` + `PandaNode` |
| BVH | 层次包围体，快速剔除子树 | `get_bounds()` + `compute_external_bounds()` |
| 脏标记 | 延迟计算，只在需要时更新 | `_last_bounds_update != _next_update` |
| 懒惰求值 | 修改时只标记，查询时才计算 | `mark_bounds_stale()` + `update_cached()` |
| 视锥变换 | 将视锥变换到局部空间 | `apply_transform()` + `xform(inverse_mat)` |
| DrawMask | 位掩码控制多相机可见性 | `_draw_control_mask` + `_draw_show_mask` |

**核心设计哲学**：
1. **空间局部性**：相邻物体组织在同一子树，包围体紧密
2. **时间局部性**：脏标记 + 懒惰求值，避免重复计算
3. **保守正确性**：奇异矩阵时放弃剔除，宁可多画不可漏画
4. **线程安全**：Pipeline Cycler 保证多线程下的数据一致性