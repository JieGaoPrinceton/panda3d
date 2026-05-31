# 专题12：LOD 与流式加载

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

大型 3D 场景面临两个核心矛盾：

| 矛盾 | 描述 |
|------|------|
| **质量 vs 性能** | 高精度模型消耗大量 GPU 资源，但远处物体不需要高精度 |
| **内存 vs 加载时间** | 一次性加载所有资源会耗尽内存，但按需加载会产生卡顿 |

**LOD（Level of Detail）** 解决质量 vs 性能矛盾：根据距离自动切换模型精度。

**流式加载（Streaming）** 解决内存 vs 加载时间矛盾：在后台异步加载即将需要的资源，卸载不再需要的资源。

典型应用场景：
```
开放世界游戏：
  玩家附近 (0-50m)   → 高精度模型 (LOD0, 50k 三角形)
  中距离 (50-200m)   → 中精度模型 (LOD1, 5k 三角形)
  远距离 (200-500m)  → 低精度模型 (LOD2, 500 三角形)
  极远处 (500m+)     → 广告牌/剔除

  同时：
  玩家前方区域 → 预加载
  玩家身后区域 → 卸载
```

---

## 2. 数学原理

### 2.1 屏幕空间误差（Screen Space Error）

LOD 切换的理论基础是**屏幕空间误差**：模型简化引入的几何误差在屏幕上的投影大小。

设物体到相机距离为 $d$，模型的世界空间误差为 $\epsilon$，相机垂直 FOV 为 $\theta$，屏幕高度为 $H$：

$$
\text{SSE} = \frac{\epsilon \cdot H}{2d \cdot \tan(\theta/2)}
$$

当 SSE 小于阈值（通常 1-2 像素）时，切换到更低精度的 LOD。

**距离阈值推导**：给定最大允许 SSE $= \tau$，切换距离为：

$$
d_{switch} = \frac{\epsilon \cdot H}{2\tau \cdot \tan(\theta/2)}
$$

### 2.2 LOD 切换的滞后（Hysteresis）

为避免在切换距离附近频繁抖动（LOD popping），引入滞后区间：

$$
d_{in} > d_{out}
$$

- 从远到近：在 $d_{in}$ 处切换到更高精度
- 从近到远：在 $d_{out}$ 处切换到更低精度

Panda3D 的 [`LODNode`](panda/src/pgraphnodes/lodNode.h:29) 正是使用这种 in/out 双阈值设计。

### 2.3 FadeLOD 的 Alpha 过渡

硬切换会产生明显的"跳变"（LOD popping）。FadeLOD 使用 Alpha 混合平滑过渡：

在过渡时间 $T$ 内，同时渲染新旧两个 LOD：

$$
\alpha_{new}(t) = \frac{t}{T}, \quad \alpha_{old}(t) = 1 - \frac{t}{T}
$$

最终颜色：
$$
C = \alpha_{new} \cdot C_{LOD_{new}} + \alpha_{old} \cdot C_{LOD_{old}}
$$

代价：过渡期间 draw call 数量翻倍。

### 2.4 流式加载的预测模型

**基于速度的预测**：

$$
\text{预加载距离} = v \cdot t_{load} + d_{activate}
$$

其中 $v$ 是玩家速度，$t_{load}$ 是资源加载时间，$d_{activate}$ 是激活距离。

**优先级队列**：

$$
\text{priority}(chunk) = \frac{1}{d_{chunk}} \cdot \text{visibility}(chunk)
$$

距离越近、可见性越高的区块优先加载。

### 2.5 网格简化算法

**QEM（Quadric Error Metrics）**：Garland-Heckbert 算法，最常用的网格简化方法。

每个顶点 $v$ 关联一个误差二次型矩阵 $Q$：

$$
\Delta(v) = v^T Q v
$$

合并边 $(v_1, v_2)$ 时，新顶点位置最小化：

$$
v_{new} = \arg\min_{v} (v^T (Q_1 + Q_2) v)
$$

解析解：

$$
v_{new} = (Q_1 + Q_2)^{-1} \begin{bmatrix} 0 \\ 0 \\ 0 \\ 1 \end{bmatrix}
$$

---

## 3. 工程实践

### 3.1 LOD 层级设计

| LOD 级别 | 距离范围 | 三角形数 | 纹理分辨率 |
|----------|----------|----------|------------|
| LOD0（最高） | 0-50m | 50,000 | 2048×2048 |
| LOD1 | 50-150m | 5,000 | 1024×1024 |
| LOD2 | 150-400m | 500 | 512×512 |
| LOD3（最低） | 400-800m | 50 | 256×256 |
| 剔除 | 800m+ | 0 | — |

**经验法则**：每级 LOD 减少 80-90% 的三角形数。

### 3.2 广告牌（Billboard）技术

极远处的物体可以用始终朝向相机的 2D 图片替代 3D 模型：

```
LOD3 → 广告牌（Billboard）
  - 始终朝向相机（Y 轴旋转）
  - 只有 2 个三角形
  - 视觉上与低精度 3D 模型相近
```

Panda3D 的 `BillboardEffect` 实现此功能。

### 3.3 流式加载架构

```
主线程（App）:
  ├── 每帧检查玩家位置
  ├── 计算需要加载/卸载的区块
  └── 向加载队列提交请求

后台线程（Loader）:
  ├── 从队列取出请求
  ├── 从磁盘读取文件
  ├── 解压/解码数据
  └── 将结果放入完成队列

主线程（App）:
  ├── 从完成队列取出结果
  └── 将模型添加到场景图
```

### 3.4 BAM 格式与缓存

Panda3D 的 BAM（Binary Animation and Models）格式是优化的二进制格式：
- 比 EGG 格式加载快 10-100x
- 支持增量加载
- 可以预先计算包围体、法线等

---

## 4. Panda3D 源码剖析

### 4.1 LODNode：距离切换节点

[`lodNode.h:29`](panda/src/pgraphnodes/lodNode.h:29)

```cpp
class EXPCL_PANDA_PGRAPHNODES LODNode : public PandaNode {
  // 核心数据：Switch 数组
  class Switch {
    PN_stdfloat _in;   // 切入距离（从远到近，在此距离激活）
    PN_stdfloat _out;  // 切出距离（从近到远，在此距离停用）
    // in > out，形成滞后区间

    bool in_range(PN_stdfloat dist) const;
    bool in_range_2(PN_stdfloat dist2) const;  // 使用距离平方（避免 sqrt）
  };

  // CData（流水线循环数据）
  class CData : public CycleData {
    LPoint3 _center;           // LOD 中心点（世界空间）
    SwitchVector _switch_vector; // 各级 LOD 的切换距离
    size_t _lowest, _highest;  // 最低/最高精度索引
    bool _got_force_switch;    // 是否强制使用某级 LOD
    int _force_switch;         // 强制使用的 LOD 索引
    PN_stdfloat _lod_scale;    // LOD 缩放因子（调整切换距离）
  };

  // 关键方法
  void add_switch(PN_stdfloat in, PN_stdfloat out);
  bool cull_callback(CullTraverser *trav, CullTraverserData &data);
  int compute_child(CullTraverser *trav, CullTraverserData &data);
};
```

**`compute_child()` 核心逻辑**（伪代码）：

```cpp
int LODNode::compute_child(CullTraverser *trav, CullTraverserData &data) {
  // 1. 计算相机到 LOD 中心的距离
  CPT(TransformState) rel_transform = get_rel_transform(trav, data);
  LPoint3 center = cdata->_center * rel_transform->get_mat();
  PN_stdfloat dist2 = center.length_squared();

  // 2. 应用 LOD 缩放（相机的 lod_scale * 节点的 lod_scale）
  PN_stdfloat lod_scale = trav->get_scene()->get_camera_node()->get_lod_scale()
                        * cdata->_lod_scale;
  dist2 /= (lod_scale * lod_scale);

  // 3. 遍历 Switch 数组，找到匹配的 LOD 级别
  for (int i = 0; i < num_switches; i++) {
    if (cdata->_switch_vector[i].in_range_2(dist2)) {
      return i;  // 返回子节点索引
    }
  }
  return -1;  // 不在任何范围内，不渲染
}
```

### 4.2 FadeLODNode：平滑过渡

[`fadeLodNode.h:24`](panda/src/pgraphnodes/fadeLodNode.h:24)

```cpp
class EXPCL_PANDA_PGRAPHNODES FadeLODNode : public LODNode {
  PN_stdfloat _fade_time;        // 过渡时间（秒）
  std::string _fade_bin_name;    // 过渡期间使用的渲染 Bin
  int _fade_bin_draw_order;      // Bin 内排序
  int _fade_state_override;      // 状态覆盖优先级

  // 过渡状态（新旧 LOD 的 Alpha 值）
  CPT(RenderState) _fade_1_new_state;  // 新 LOD：alpha 从 0 到 1
  CPT(RenderState) _fade_1_old_state;  // 旧 LOD：alpha 从 1 到 0
  CPT(RenderState) _fade_2_new_state;
  CPT(RenderState) _fade_2_old_state;

  // 过渡数据存储在 AuxSceneData 中（每个相机独立）
  // FadeLODNodeData 记录当前过渡进度
};
```

### 4.3 Camera 的 LOD 控制

[`camera.h:74`](panda/src/pgraph/camera.h:74)

```cpp
class Camera : public LensNode {
  // LOD 中心：计算 LOD 距离时使用的参考点
  // 默认是相机位置，可以设置为其他点（如玩家位置）
  NodePath _lod_center;

  // LOD 缩放：全局调整所有 LOD 的切换距离
  // 值越大，越早切换到低精度（性能优先）
  // 值越小，越晚切换到低精度（质量优先）
  PN_stdfloat _lod_scale;
};
```

### 4.4 Loader：异步加载系统

Panda3D 的 `Loader` 类支持异步加载：

```cpp
// direct/src/showbase/Loader.py（Python 层）
class Loader:
    def loadModel(self, modelPath, callback=None, extraArgs=[],
                  priority=None, loaderOptions=None, noCache=None,
                  allowInstance=False, okMissing=None, blocking=None):
        """
        如果 callback 不为 None，则异步加载
        否则同步加载（阻塞）
        """
        if callback is None:
            # 同步加载
            return self._load_model_sync(modelPath, loaderOptions)
        else:
            # 异步加载：提交到后台线程
            request = self._make_async_request(modelPath, loaderOptions)
            request.set_done_callback(callback, extraArgs)
            self._loader.load_async(request)
```

## 5. 代码演示

### 5.1 Python：基本 LOD 设置

```python
"""
LODNode 基本用法：根据距离切换模型精度
"""
from direct.showbase.ShowBase import ShowBase
from panda3d.core import LODNode, NodePath, Point3

class LODDemo(ShowBase):
    def __init__(self):
        super().__init__()

        # ── 方式1：手动创建 LODNode ───────────────────────────────────────────
        lod_node = LODNode("tree_lod")
        lod_np = self.render.attachNewNode(lod_node)
        lod_np.setPos(0, 50, 0)

        # 加载不同精度的模型
        # 注意：子节点顺序必须与 add_switch 顺序一致
        high_detail  = self.loader.loadModel("models/tree_high")   # LOD0
        mid_detail   = self.loader.loadModel("models/tree_mid")    # LOD1
        low_detail   = self.loader.loadModel("models/tree_low")    # LOD2
        billboard    = self.loader.loadModel("models/tree_billboard")  # LOD3

        high_detail.reparentTo(lod_np)
        mid_detail.reparentTo(lod_np)
        low_detail.reparentTo(lod_np)
        billboard.reparentTo(lod_np)

        # 添加切换距离：add_switch(in_distance, out_distance)
        # in > out，形成滞后区间防止抖动
        # 子节点0（high_detail）：0-55m 可见
        lod_node.addSwitch(55, 0)     # in=55, out=0
        # 子节点1（mid_detail）：50-160m 可见
        lod_node.addSwitch(160, 50)   # in=160, out=50
        # 子节点2（low_detail）：150-420m 可见
        lod_node.addSwitch(420, 150)  # in=420, out=150
        # 子节点3（billboard）：400-850m 可见
        lod_node.addSwitch(850, 400)  # in=850, out=400

        # 设置 LOD 中心（默认是节点原点）
        lod_node.setCenter(Point3(0, 0, 1))  # 树的中心高度

        # ── 方式2：使用 NodePath 的便捷接口 ──────────────────────────────────
        # Panda3D 提供了更简洁的 LOD 接口
        lod2 = self.render.attachNewNode(LODNode("rock_lod"))
        lod2.setPos(20, 30, 0)

        # 直接加载并添加 LOD 级别
        for model_path, switch_in, switch_out in [
            ("models/rock_high",  40,   0),
            ("models/rock_mid",  120,  35),
            ("models/rock_low",  300, 110),
        ]:
            model = self.loader.loadModel(model_path)
            model.reparentTo(lod2)
            lod2.node().addSwitch(switch_in, switch_out)

        # ── LOD 调试：显示切换范围 ────────────────────────────────────────────
        # 显示所有 LOD 级别（调试用）
        lod_node.showAllSwitches()

        # 只显示特定级别
        # lod_node.showSwitch(0)  # 只显示 LOD0

        # 强制使用特定 LOD（调试/截图用）
        # lod_node.forceSwitch(1)  # 强制使用 LOD1
        # lod_node.clearForceSwitch()  # 取消强制

        # ── 全局 LOD 缩放 ─────────────────────────────────────────────────────
        # 调整相机的 LOD 缩放因子
        # 值 > 1：更早切换到低精度（性能优先）
        # 值 < 1：更晚切换到低精度（质量优先）
        self.cam.node().setLodScale(1.5)  # 性能模式

        # 设置 LOD 参考点（默认是相机位置）
        # 可以设置为玩家位置，使 LOD 基于玩家距离而非相机距离
        # self.cam.node().setLodCenter(player_np)
```

### 5.2 Python：FadeLODNode（平滑过渡）

```python
"""
FadeLODNode：LOD 切换时使用 Alpha 淡入淡出，避免突变
"""
from direct.showbase.ShowBase import ShowBase
from panda3d.core import FadeLODNode, NodePath

class FadeLODDemo(ShowBase):
    def __init__(self):
        super().__init__()

        # 创建 FadeLODNode
        fade_lod = FadeLODNode("fade_tree")
        fade_np = self.render.attachNewNode(fade_lod)
        fade_np.setPos(0, 30, 0)

        # 设置过渡时间（秒）
        fade_lod.setFadeTime(0.5)  # 0.5秒内完成过渡

        # 设置过渡期间使用的渲染 Bin
        # 过渡时两个 LOD 都需要渲染，放入透明 Bin
        fade_lod.setFadeBin("transparent", 0)

        # 添加模型（与 LODNode 相同）
        high = self.loader.loadModel("models/tree_high")
        low  = self.loader.loadModel("models/tree_low")
        high.reparentTo(fade_np)
        low.reparentTo(fade_np)

        fade_lod.addSwitch(60, 0)
        fade_lod.addSwitch(200, 55)

        # 注意：FadeLODNode 需要透明度支持
        # 确保模型材质支持 Alpha 混合
        fade_np.setTransparency(True)
```

### 5.3 Python：流式加载系统

```python
"""
流式加载：根据玩家位置动态加载/卸载区块
"""
from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from panda3d.core import NodePath, Point3, Vec3
import math
import queue
import threading

class StreamingWorld(ShowBase):
    """
    简单的区块流式加载系统
    将世界划分为固定大小的区块，根据玩家位置加载/卸载
    """

    CHUNK_SIZE = 100.0      # 每个区块的世界空间大小
    LOAD_RADIUS = 3         # 加载半径（区块数）
    UNLOAD_RADIUS = 5       # 卸载半径（区块数）

    def __init__(self):
        super().__init__()

        self.player_pos = Point3(0, 0, 0)
        self.loaded_chunks = {}    # {(cx, cy): NodePath}
        self.loading_chunks = set()  # 正在加载的区块
        self._load_queue = queue.PriorityQueue()
        self._done_queue = queue.Queue()

        # 启动后台加载线程
        self._loader_thread = threading.Thread(
            target=self._loader_worker, daemon=True
        )
        self._loader_thread.start()

        # 主循环任务
        self.taskMgr.add(self._update_streaming, "UpdateStreaming")
        self.taskMgr.add(self._apply_loaded_chunks, "ApplyChunks")

        # 模拟玩家移动
        self.taskMgr.add(self._move_player, "MovePlayer")
        self._move_angle = 0.0

    def _world_to_chunk(self, pos):
        """将世界坐标转换为区块坐标"""
        cx = int(math.floor(pos.x / self.CHUNK_SIZE))
        cy = int(math.floor(pos.y / self.CHUNK_SIZE))
        return (cx, cy)

    def _chunk_to_world(self, cx, cy):
        """将区块坐标转换为世界坐标（区块中心）"""
        x = (cx + 0.5) * self.CHUNK_SIZE
        y = (cy + 0.5) * self.CHUNK_SIZE
        return Point3(x, y, 0)

    def _chunk_distance(self, cx, cy, player_cx, player_cy):
        """计算区块到玩家区块的距离"""
        return math.sqrt((cx - player_cx)**2 + (cy - player_cy)**2)

    def _update_streaming(self, task):
        """每帧检查需要加载/卸载的区块"""
        player_cx, player_cy = self._world_to_chunk(self.player_pos)

        # 检查需要加载的区块
        for dx in range(-self.LOAD_RADIUS, self.LOAD_RADIUS + 1):
            for dy in range(-self.LOAD_RADIUS, self.LOAD_RADIUS + 1):
                cx, cy = player_cx + dx, player_cy + dy
                dist = self._chunk_distance(cx, cy, player_cx, player_cy)

                if dist <= self.LOAD_RADIUS:
                    if (cx, cy) not in self.loaded_chunks and \
                       (cx, cy) not in self.loading_chunks:
                        # 优先级：距离越近优先级越高（负数，因为 PriorityQueue 最小优先）
                        priority = dist
                        self._load_queue.put((priority, (cx, cy)))
                        self.loading_chunks.add((cx, cy))

        # 检查需要卸载的区块
        to_unload = []
        for (cx, cy), chunk_np in self.loaded_chunks.items():
            dist = self._chunk_distance(cx, cy, player_cx, player_cy)
            if dist > self.UNLOAD_RADIUS:
                to_unload.append((cx, cy))

        for chunk_key in to_unload:
            self._unload_chunk(chunk_key)

        return Task.cont

    def _loader_worker(self):
        """后台线程：从磁盘加载区块数据"""
        while True:
            try:
                priority, (cx, cy) = self._load_queue.get(timeout=0.1)
                # 模拟加载：实际项目中这里读取文件
                chunk_data = self._load_chunk_data(cx, cy)
                self._done_queue.put(((cx, cy), chunk_data))
            except queue.Empty:
                continue

    def _load_chunk_data(self, cx, cy):
        """
        后台线程中执行：读取区块数据
        注意：不能操作场景图！
        """
        import time
        # 模拟文件读取延迟
        time.sleep(0.05)
        # 返回区块描述数据（不是 NodePath）
        return {
            "cx": cx, "cy": cy,
            "model_path": "models/environment",
            "pos": self._chunk_to_world(cx, cy),
        }

    def _apply_loaded_chunks(self, task):
        """主线程：将加载完成的区块添加到场景图"""
        while not self._done_queue.empty():
            try:
                (cx, cy), chunk_data = self._done_queue.get_nowait()
                self._create_chunk_node(cx, cy, chunk_data)
                self.loading_chunks.discard((cx, cy))
            except queue.Empty:
                break
        return Task.cont

    def _create_chunk_node(self, cx, cy, data):
        """主线程：创建区块场景节点"""
        if (cx, cy) in self.loaded_chunks:
            return  # 已经加载

        # 在主线程中安全地操作场景图
        chunk_np = self.render.attachNewNode(f"chunk_{cx}_{cy}")
        chunk_np.setPos(data["pos"])

        # 加载模型（同步，因为数据已在内存中）
        model = self.loader.loadModel(data["model_path"])
        if model:
            model.reparentTo(chunk_np)

        self.loaded_chunks[(cx, cy)] = chunk_np

    def _unload_chunk(self, chunk_key):
        """卸载区块"""
        if chunk_key in self.loaded_chunks:
            chunk_np = self.loaded_chunks.pop(chunk_key)
            chunk_np.removeNode()  # 从场景图移除并释放内存

    def _move_player(self, task):
        """模拟玩家移动（圆形路径）"""
        dt = globalClock.getDt()
        self._move_angle += dt * 20  # 每秒移动 20 度
        radius = 150.0
        x = math.cos(math.radians(self._move_angle)) * radius
        y = math.sin(math.radians(self._move_angle)) * radius
        self.player_pos = Point3(x, y, 0)
        return Task.cont
```

### 5.4 Python：使用 Panda3D 内置异步加载

```python
"""
使用 Panda3D 内置的异步加载器（推荐方式）
"""
from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from panda3d.core import LoaderOptions, NodePath

class AsyncLoadingDemo(ShowBase):
    def __init__(self):
        super().__init__()

        self._pending = {}  # {request_id: callback}

        # ── 基本异步加载 ──────────────────────────────────────────────────────
        self.loader.loadModel(
            "models/environment",
            callback=self._on_env_loaded,
        )

        # ── 批量异步加载 ──────────────────────────────────────────────────────
        models_to_load = [
            "models/tree_high",
            "models/tree_mid",
            "models/tree_low",
        ]
        self._lod_models = [None] * len(models_to_load)
        self._lod_loaded_count = 0

        for i, path in enumerate(models_to_load):
            self.loader.loadModel(
                path,
                callback=self._on_lod_loaded,
                extraArgs=[i],
            )

        # ── 带优先级的加载 ────────────────────────────────────────────────────
        options = LoaderOptions()
        # LoaderOptions 可以控制缓存行为
        # options.setFlags(LoaderOptions.LF_no_cache)  # 不使用缓存

        self.loader.loadModel(
            "models/important_model",
            callback=self._on_important_loaded,
            loaderOptions=options,
        )

    def _on_env_loaded(self, model):
        """环境模型加载完成"""
        if model:
            model.reparentTo(self.render)
            print("环境加载完成")
        else:
            print("环境加载失败")

    def _on_lod_loaded(self, model, index):
        """LOD 模型加载完成"""
        self._lod_models[index] = model
        self._lod_loaded_count += 1

        if self._lod_loaded_count >= len(self._lod_models):
            # 所有 LOD 级别都加载完成
            self._setup_lod()

    def _setup_lod(self):
        """所有 LOD 模型就绪，创建 LOD 节点"""
        from panda3d.core import LODNode
        lod_node = LODNode("tree")
        lod_np = self.render.attachNewNode(lod_node)

        distances = [(60, 0), (180, 55), (500, 170)]
        for i, (model, (switch_in, switch_out)) in enumerate(
            zip(self._lod_models, distances)
        ):
            if model:
                model.reparentTo(lod_np)
                lod_node.addSwitch(switch_in, switch_out)

        print("LOD 树创建完成")

    def _on_important_loaded(self, model):
        if model:
            model.reparentTo(self.render)


# ── 预加载系统 ────────────────────────────────────────────────────────────────
class PreloadSystem(ShowBase):
    """
    预加载系统：在游戏开始前预加载所有资源
    显示加载进度条
    """
    def __init__(self):
        super().__init__()

        self._resources = {
            "environment": None,
            "player": None,
            "enemies": [],
        }
        self._total = 5
        self._loaded = 0

        self._show_loading_ui()
        self._start_preload()

    def _show_loading_ui(self):
        from direct.gui.DirectGui import DirectWaitBar, DirectLabel
        self._bar = DirectWaitBar(
            text="加载资源...",
            value=0,
            pos=(0, 0, -0.1),
            scale=0.8,
        )
        self._label = DirectLabel(
            text="正在初始化...",
            pos=(0, 0, 0.1),
            scale=0.07,
        )

    def _start_preload(self):
        """开始预加载所有资源"""
        assets = [
            ("models/environment", self._on_env_ready),
            ("models/player",      self._on_player_ready),
            ("models/enemy1",      lambda m: self._on_enemy_ready(m, 0)),
            ("models/enemy2",      lambda m: self._on_enemy_ready(m, 1)),
            ("models/enemy3",      lambda m: self._on_enemy_ready(m, 2)),
        ]
        for path, callback in assets:
            self.loader.loadModel(path, callback=callback)

    def _update_progress(self, name):
        self._loaded += 1
        progress = (self._loaded / self._total) * 100
        self._bar["value"] = progress
        self._label["text"] = f"已加载: {name}"

        if self._loaded >= self._total:
            self._on_all_loaded()

    def _on_env_ready(self, model):
        self._resources["environment"] = model
        self._update_progress("环境")

    def _on_player_ready(self, model):
        self._resources["player"] = model
        self._update_progress("玩家")

    def _on_enemy_ready(self, model, index):
        self._resources["enemies"].append(model)
        self._update_progress(f"敌人{index+1}")

    def _on_all_loaded(self):
        """所有资源加载完成，开始游戏"""
        self._bar.destroy()
        self._label.destroy()
        self._start_game()

    def _start_game(self):
        """将预加载的资源添加到场景"""
        if self._resources["environment"]:
            self._resources["environment"].reparentTo(self.render)
        print("游戏开始！")
```

### 5.5 Python：LOD 与流式加载结合

```python
"""
完整示例：LOD + 流式加载的结合使用
"""
from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from panda3d.core import LODNode, FadeLODNode, NodePath, Point3
import math
import queue
import threading

class OpenWorldDemo(ShowBase):
    """
    开放世界演示：
    - 近处：高精度 LOD
    - 中距离：低精度 LOD
    - 远处：广告牌
    - 极远处：流式卸载
    """

    CHUNK_SIZE = 200.0
    LOAD_RADIUS = 2
    UNLOAD_RADIUS = 4

    def __init__(self):
        super().__init__()

        self.loaded_chunks = {}
        self._load_queue = queue.PriorityQueue()
        self._done_queue = queue.Queue()
        self.player_pos = Point3(0, 0, 0)

        # 启动加载线程
        threading.Thread(target=self._loader_worker, daemon=True).start()

        # 任务
        self.taskMgr.add(self._update, "Update")
        self.taskMgr.add(self._apply_chunks, "ApplyChunks")

        # 相机 LOD 设置
        self.cam.node().setLodScale(1.2)  # 稍微偏向性能

    def _create_lod_tree(self, parent, pos):
        """创建带 LOD 的树"""
        # 使用 FadeLODNode 实现平滑过渡
        lod = FadeLODNode("tree")
        lod.setFadeTime(0.3)
        lod_np = parent.attachNewNode(lod)
        lod_np.setPos(pos)

        # 高精度（近处）
        high = self.loader.loadModel("models/environment")
        high.setScale(0.3)
        high.reparentTo(lod_np)
        lod.addSwitch(80, 0)

        # 低精度（中距离）
        low = self.loader.loadModel("models/environment")
        low.setScale(0.3)
        low.reparentTo(lod_np)
        lod.addSwitch(250, 70)

        return lod_np

    def _loader_worker(self):
        while True:
            try:
                _, (cx, cy) = self._load_queue.get(timeout=0.1)
                import time; time.sleep(0.02)  # 模拟 I/O
                self._done_queue.put((cx, cy))
            except queue.Empty:
                continue

    def _update(self, task):
        # 模拟玩家移动
        t = task.time
        self.player_pos = Point3(
            math.cos(t * 0.3) * 300,
            math.sin(t * 0.3) * 300,
            0
        )

        # 更新流式加载
        pcx = int(math.floor(self.player_pos.x / self.CHUNK_SIZE))
        pcy = int(math.floor(self.player_pos.y / self.CHUNK_SIZE))

        for dx in range(-self.LOAD_RADIUS, self.LOAD_RADIUS + 1):
            for dy in range(-self.LOAD_RADIUS, self.LOAD_RADIUS + 1):
                cx, cy = pcx + dx, pcy + dy
                dist = math.sqrt(dx*dx + dy*dy)
                if dist <= self.LOAD_RADIUS and (cx, cy) not in self.loaded_chunks:
                    self._load_queue.put((dist, (cx, cy)))
                    self.loaded_chunks[(cx, cy)] = None  # 标记为加载中

        # 卸载远处区块
        to_remove = [
            k for k, v in self.loaded_chunks.items()
            if v is not None and math.sqrt(
                (k[0]-pcx)**2 + (k[1]-pcy)**2
            ) > self.UNLOAD_RADIUS
        ]
        for k in to_remove:
            self.loaded_chunks[k].removeNode()
            del self.loaded_chunks[k]

        return Task.cont

    def _apply_chunks(self, task):
        while not self._done_queue.empty():
            try:
                cx, cy = self._done_queue.get_nowait()
                if (cx, cy) in self.loaded_chunks:
                    chunk = self.render.attachNewNode(f"chunk_{cx}_{cy}")
                    cx_world = (cx + 0.5) * self.CHUNK_SIZE
                    cy_world = (cy + 0.5) * self.CHUNK_SIZE
                    chunk.setPos(cx_world, cy_world, 0)

                    # 在区块中放置带 LOD 的树
                    import random
                    rng = random.Random(cx * 1000 + cy)
                    for _ in range(5):
                        x = rng.uniform(-self.CHUNK_SIZE/2, self.CHUNK_SIZE/2)
                        y = rng.uniform(-self.CHUNK_SIZE/2, self.CHUNK_SIZE/2)
                        self._create_lod_tree(chunk, Point3(x, y, 0))

                    self.loaded_chunks[(cx, cy)] = chunk
            except queue.Empty:
                break
        return Task.cont
```

---

## 6. 性能优化

### 6.1 LOD 切换距离调优

```python
# ── 基于屏幕空间误差计算切换距离 ─────────────────────────────────────────────
import math

def compute_lod_distance(world_error, screen_height, fov_deg, max_sse_pixels=2.0):
    """
    根据屏幕空间误差计算 LOD 切换距离

    world_error: 模型简化引入的世界空间误差（米）
    screen_height: 屏幕高度（像素）
    fov_deg: 垂直 FOV（度）
    max_sse_pixels: 最大允许屏幕空间误差（像素）
    """
    fov_rad = math.radians(fov_deg)
    distance = (world_error * screen_height) / (2 * max_sse_pixels * math.tan(fov_rad / 2))
    return distance

# 示例：树模型，LOD0→LOD1 的世界误差约 0.5m
# 屏幕 1080p，FOV 60度，允许 2 像素误差
d = compute_lod_distance(0.5, 1080, 60, 2.0)
print(f"LOD0→LOD1 切换距离: {d:.1f}m")  # 约 93m
```

### 6.2 LOD 性能对比

```
场景：1000 棵树，玩家在中心

无 LOD（全部 LOD0）：
  三角形数: 50,000,000
  帧时间:   45ms (22 FPS)

有 LOD（4级）：
  LOD0 (0-55m):   ~20棵树  × 50,000 = 1,000,000 三角形
  LOD1 (55-160m): ~80棵树  × 5,000  =   400,000 三角形
  LOD2 (160-420m):~300棵树 × 500    =   150,000 三角形
  LOD3 (420-850m):~600棵树 × 50     =    30,000 三角形
  总计: 1,580,000 三角形
  帧时间: 8ms (125 FPS)
  提升: 5.6x
```

### 6.3 流式加载最佳实践

```python
# ❌ 错误：在主线程同步加载（卡顿）
def bad_load_chunk(cx, cy):
    model = loader.loadModel("models/chunk")  # 阻塞主线程！
    model.reparentTo(render)

# ✅ 正确：异步加载
def good_load_chunk(cx, cy):
    loader.loadModel(
        "models/chunk",
        callback=lambda m: _on_chunk_loaded(m, cx, cy),
    )

# ❌ 错误：每帧检查所有区块（O(n^2)）
def bad_update():
    for chunk in all_possible_chunks:  # 可能有数千个
        if distance(chunk, player) < load_radius:
            load(chunk)

# ✅ 正确：只检查玩家周围的区块（O(r^2)）
def good_update():
    pcx, pcy = world_to_chunk(player_pos)
    for dx in range(-LOAD_RADIUS, LOAD_RADIUS + 1):
        for dy in range(-LOAD_RADIUS, LOAD_RADIUS + 1):
            check_chunk(pcx + dx, pcy + dy)
```

### 6.4 内存管理

```python
# 使用 ModelPool 缓存已加载的模型（避免重复加载）
from panda3d.core import ModelPool

# 检查模型是否已在缓存中
if ModelPool.hasModel("models/tree"):
    model = ModelPool.loadModel("models/tree")
else:
    model = loader.loadModel("models/tree")

# 卸载时从缓存中移除
ModelPool.releaseModel("models/tree")

# 清空所有缓存（场景切换时）
ModelPool.garbageCollect()
```

---

## 小结

| 知识点 | 核心要点 |
|--------|----------|
| **LODNode** | in/out 双阈值防抖动，`compute_child()` 基于距离平方 |
| **FadeLODNode** | Alpha 混合平滑过渡，过渡期间 draw call 翻倍 |
| **屏幕空间误差** | LOD 切换距离的理论依据，SSE = ε·H / (2d·tan(θ/2)) |
| **lod_scale** | 相机/节点的 LOD 缩放因子，快速调整性能/质量平衡 |
| **流式加载** | 后台线程读取数据，主线程应用到场景图 |
| **区块系统** | 将世界划分为固定大小区块，按距离加载/卸载 |
| **优先级队列** | 距离近、可见性高的区块优先加载 |
| **ModelPool** | 缓存已加载模型，避免重复磁盘读取 |

### 关键设计原则

1. **LOD 切换距离基于屏幕空间误差**：不要随意设置距离，应根据模型误差和屏幕分辨率计算
2. **使用距离平方比较**：避免 `sqrt()` 开销，`in_range_2()` 使用距离平方
3. **FadeLOD 有代价**：过渡期间渲染两个 LOD，仅在视觉质量要求高时使用
4. **流式加载必须异步**：任何磁盘 I/O 都不能在主线程中同步执行
5. **卸载半径 > 加载半径**：防止在边界处频繁加载/卸载（滞后设计）
6. **区块大小权衡**：太小→管理开销大；太大→内存浪费、加载时间长

### 与其他专题的关联

- **专题02（场景图）**：LODNode 是 PandaNode 的子类，参与场景图遍历
- **专题08（纹理管理）**：流式加载也适用于纹理（Mipmap 流式加载）
- **专题10（多线程）**：流式加载依赖后台线程和命令队列模式
- **专题11（后处理）**：LOD 减少几何体，后处理减少像素计算，共同优化性能
