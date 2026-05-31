# 专题14：精度与数值稳定性

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

3D 引擎中的数值精度问题是最隐蔽、最难调试的 Bug 来源之一：

| 问题 | 描述 | 典型症状 |
|------|------|----------|
| **浮点精度** | float 只有 ~7 位有效数字 | 远处物体抖动（Z-fighting） |
| **大世界坐标** | 坐标值过大导致精度丢失 | 玩家在 10km 外时物体抖动 |
| **矩阵累积误差** | 多次矩阵乘法累积误差 | 骨骼动画漂移 |
| **四元数漂移** | 四元数归一化误差累积 | 旋转轴偏移 |
| **深度冲突** | 两个面深度值相同 | Z-fighting 闪烁 |
| **碰撞精度** | 浮点误差导致穿透 | 物体穿过薄墙 |

**核心矛盾**：
- `float`（32位）：GPU 原生支持，但精度有限（约 7 位十进制）
- `double`（64位）：精度高，但 GPU 不原生支持，CPU 计算慢

---

## 2. 数学原理

### 2.1 IEEE 754 浮点数结构

32位 `float` 的二进制表示：

```
符号(1位) | 指数(8位) | 尾数(23位)
    S     |  EEEEEEEE | MMMMMMMMMMMMMMMMMMMMMMM

值 = (-1)^S × 2^(E-127) × (1 + M/2^23)
```

**精度分析**：
- 尾数 23 位 → 约 $2^{-23} \approx 1.2 \times 10^{-7}$ 相对精度
- 在坐标值 $x = 10000$ 时，最小可分辨差值 = $10000 \times 10^{-7} = 0.001$（1毫米）
- 在坐标值 $x = 100000$ 时，最小可分辨差值 = $0.01$（1厘米）

**大世界问题**：当玩家坐标达到 $10^5$ 米（100km）时，float 精度只有 1cm，物理模拟和渲染都会出现明显抖动。

### 2.2 Z-Fighting 的数学分析

深度缓冲的精度分布是**非线性**的（对数分布）：

**OpenGL 深度值**（NDC 深度 $z_{ndc}$）：

$$
z_{ndc} = \frac{f+n}{f-n} - \frac{2fn}{(f-n) \cdot z_{view}}
$$

**深度精度**（相邻深度值之间的最小可分辨距离）：

$$
\Delta z_{view} \approx \frac{z_{view}^2}{fn} \cdot \frac{1}{2^{depth\_bits}}
$$

这意味着：
- 近处（$z_{view} = n$）：精度最高
- 远处（$z_{view} = f$）：精度最低，$\Delta z \propto z^2$

**Z-Fighting 条件**：两个面的深度差 $< \Delta z_{view}$

**解决方案**：增大近裁剪面 $n$（对精度影响最大）：

$$
\text{精度} \propto \frac{1}{f/n}
$$

将 $n$ 从 0.1 增大到 1.0，精度提升 10 倍。

### 2.3 反转深度（Reversed-Z）

传统深度缓冲将精度集中在近处，但远处精度极差。**反转深度**技术将深度值反转：

$$
z_{reversed} = 1 - z_{traditional}
$$

配合浮点深度缓冲，精度分布更均匀：

| 方法 | 近处精度 | 远处精度 |
|------|----------|----------|
| 传统整数深度 | 高 | 极低 |
| 反转浮点深度 | 中 | 高 |

### 2.4 大世界坐标：相对坐标技术

**问题**：玩家在 $(100000, 100000, 0)$ 处，附近物体在 $(100001, 100000, 0)$，差值 1.0 但 float 精度只有 0.01。

**解决方案**：以玩家为原点，所有渲染坐标相对于玩家：

$$
\text{渲染坐标} = \text{世界坐标} - \text{玩家坐标}
$$

这样渲染坐标始终在 $[-1000, 1000]$ 范围内，float 精度足够。

**实现**：
1. 游戏逻辑使用 `double` 存储世界坐标
2. 每帧渲染前，将所有物体坐标减去相机位置
3. 相机始终在原点渲染

### 2.5 四元数归一化误差

四元数 $q = (w, x, y, z)$ 必须满足 $|q| = 1$。

每次旋转操作后，由于浮点误差，$|q|$ 会略微偏离 1：

$$
|q_{after}| = 1 + \epsilon, \quad |\epsilon| \approx 10^{-7}
$$

经过 $N$ 次操作后，误差累积：

$$
|q_N| \approx 1 + N\epsilon
$$

**解决方案**：定期重新归一化：

$$
q_{normalized} = \frac{q}{|q|}
$$

或使用快速近似归一化（牛顿迭代）：

$$
q_{normalized} \approx q \cdot \frac{3 - |q|^2}{2}
$$

---

## 3. 工程实践

### 3.1 Panda3D 的精度配置

Panda3D 支持两种精度模式：

```
# config.prc 配置
stdfloat-double true   # 使用 double 精度（默认 false）
```

当 `stdfloat-double = true` 时，`PN_stdfloat` 类型变为 `double`，所有数学运算使用双精度。

**代价**：内存翻倍，CPU 计算约慢 2x，但 GPU 仍使用 float。

### 3.2 深度缓冲配置

```python
# 增大近裁剪面（最有效的 Z-fighting 解决方案）
lens = base.cam.node().getLens()
lens.setNear(1.0)   # 默认 0.1，改为 1.0
lens.setFar(10000)  # 根据场景调整

# 使用 24 位深度缓冲（默认）
fb_props = FrameBufferProperties()
fb_props.setDepthBits(24)  # 或 32 位

# 使用浮点深度缓冲（更高精度）
fb_props.setFloatDepth(True)
```

### 3.3 大世界解决方案

**方案1：浮点原点（Floating Origin）**
- 当玩家距原点超过阈值时，将所有物体坐标平移
- 简单但会导致一帧的跳变

**方案2：相对相机渲染**
- 游戏逻辑使用 double，渲染时转换为相对坐标
- 无跳变，但需要修改渲染管线

**方案3：分层坐标系**
- 将世界分为大格子（int 坐标）+ 格子内偏移（float）
- 类似 Minecraft 的区块系统

### 3.4 碰撞精度

碰撞检测中的精度问题：

```python
# 避免使用过小的碰撞体（精度问题）
# ❌ 错误：极薄的墙（厚度 0.01）
wall = CollisionBox(Point3(0,0,0), 10, 0.01, 5)

# ✅ 正确：给墙一定厚度
wall = CollisionBox(Point3(0,0,0), 10, 0.1, 5)

# 碰撞偏移（bias）防止穿透
# 在碰撞检测中添加小的安全距离
COLLISION_BIAS = 0.001  # 1mm 安全距离
```

---

## 4. Panda3D 源码剖析

### 4.1 PN_stdfloat：可配置精度类型

Panda3D 使用 `PN_stdfloat` 作为标准浮点类型，可以在编译时或运行时切换精度：

```cpp
// dtool/src/dtoolbase/stdfloat.h
#ifdef STDFLOAT_DOUBLE
  typedef double PN_stdfloat;
#else
  typedef float PN_stdfloat;
#endif

// 所有数学类都基于 PN_stdfloat
typedef LVecBase3f LVecBase3;  // float 版本
typedef LVecBase3d LVecBase3d; // double 版本

// 当 stdfloat-double = true 时：
// LVecBase3 = LVecBase3d（double）
// 否则：
// LVecBase3 = LVecBase3f（float）
```

### 4.2 LMatrix4 的精度

```cpp
// 矩阵类型
typedef LMatrix4f LMatrix4;   // float 版本（默认）
typedef LMatrix4d LMatrix4d;  // double 版本

// 坐标系转换矩阵（预计算，避免重复计算误差）
static const LMatrix4 &convert_mat(CoordinateSystem from, CoordinateSystem to);

// 矩阵求逆（数值稳定性关键）
// Panda3D 使用 LU 分解，比直接求逆更稳定
bool invert_in_place();
```

### 4.3 LQuaternion 的归一化

```cpp
// lquaternion_src.h
class LQuaternion {
  // 归一化
  INLINE_LINMATH void normalize();

  // 检查是否已归一化
  INLINE_LINMATH bool is_unit_quat() const;

  // 球面线性插值（SLERP）
  // 注意：SLERP 要求输入四元数已归一化
  INLINE_LINMATH LQuaternion slerp(const LQuaternion &other, float t) const;
};
```

### 4.4 Lens 的深度精度控制

```cpp
// lens.h
class Lens {
  // 近/远裁剪面（影响深度精度）
  void set_near(PN_stdfloat near_distance);
  void set_far(PN_stdfloat far_distance);
  void set_near_far(PN_stdfloat near_distance, PN_stdfloat far_distance);

  // 获取投影矩阵（包含深度范围映射）
  virtual bool do_compute_projection_mat(CData *cdata);

  // 深度偏移（解决 Z-fighting）
  // 通过 DepthOffsetAttrib 实现
};
```

### 4.5 DepthOffsetAttrib：深度偏移

```cpp
// depthOffsetAttrib.h
class DepthOffsetAttrib : public RenderAttrib {
  // 为渲染对象添加深度偏移，解决 Z-fighting
  // offset > 0：向相机方向偏移（物体显示在前面）
  // offset < 0：远离相机方向偏移（物体显示在后面）

  static CPT(RenderAttrib) make(int offset = 1,
                                PN_stdfloat min_value = 0.0,
                                PN_stdfloat max_value = 1.0);
  INLINE int get_offset() const;
};
```

## 5. 代码演示

### 5.1 Python：Z-Fighting 问题与解决

```python
"""
Z-Fighting 演示与解决方案
"""
from direct.showbase.ShowBase import ShowBase
from panda3d.core import (
    DepthOffsetAttrib, DepthTestAttrib, RenderAttrib,
    CardMaker, NodePath, Vec4, LPoint3
)

class ZFightingDemo(ShowBase):
    def __init__(self):
        super().__init__()

        # ── 演示 Z-Fighting ───────────────────────────────────────────────────
        # 两个完全重叠的平面会产生 Z-Fighting
        cm = CardMaker("plane")
        cm.setFrame(-5, 5, -5, 5)

        # 平面1（红色）
        plane1 = self.render.attachNewNode(cm.generate())
        plane1.setColor(1, 0, 0, 1)
        plane1.setPos(0, 10, 0)
        plane1.setHpr(0, -90, 0)

        # 平面2（蓝色）- 与平面1完全重叠，会产生 Z-Fighting
        plane2 = self.render.attachNewNode(cm.generate())
        plane2.setColor(0, 0, 1, 1)
        plane2.setPos(0, 10, 0)  # 完全相同的位置！
        plane2.setHpr(0, -90, 0)

        # ── 解决方案1：深度偏移（DepthOffsetAttrib）────────────────────────
        # 让平面2在深度上偏移，避免与平面1冲突
        # offset=1 表示向相机方向偏移一个单位（显示在前面）
        plane2.setAttrib(DepthOffsetAttrib.make(1))

        # ── 解决方案2：调整近裁剪面 ──────────────────────────────────────────
        lens = self.cam.node().getLens()
        print(f"当前近裁剪面: {lens.getNear()}")
        print(f"当前远裁剪面: {lens.getFar()}")

        # 增大近裁剪面（最有效的方法）
        lens.setNear(1.0)   # 从默认 0.1 改为 1.0
        lens.setFar(5000)   # 根据场景调整

        # ── 解决方案3：多边形偏移（Polygon Offset）───────────────────────────
        # 在 GLSL Shader 中使用 gl_FragDepth 手动调整深度
        # 或使用 OpenGL 的 glPolygonOffset

        # ── 解决方案4：贴花（Decal）系统 ─────────────────────────────────────
        # 对于贴花（如地面标记），使用专门的贴花渲染
        # 贴花渲染在基础几何体之后，使用深度偏移
        decal = self.render.attachNewNode(cm.generate())
        decal.setColor(0, 1, 0, 0.5)
        decal.setPos(0, 10, 0.001)  # 微小偏移
        decal.setHpr(0, -90, 0)
        decal.setTransparency(True)
        # 或者使用 DepthOffsetAttrib
        decal.setAttrib(DepthOffsetAttrib.make(2))

        # ── 深度测试控制 ──────────────────────────────────────────────────────
        # 关闭深度写入（透明物体）
        plane2.setAttrib(DepthTestAttrib.make(RenderAttrib.MLessEqual))

        print("Z-Fighting 演示设置完成")
        print("解决方案：DepthOffsetAttrib + 调整近裁剪面")
```

### 5.2 Python：大世界浮点精度问题

```python
"""
大世界精度问题演示与解决方案
"""
from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from panda3d.core import LPoint3, LPoint3d, LVector3d, NodePath
import math

class LargeWorldDemo(ShowBase):
    """
    演示大世界坐标精度问题及解决方案
    使用"浮点原点"（Floating Origin）技术
    """

    # 当玩家距原点超过此距离时，重置原点
    ORIGIN_RESET_THRESHOLD = 1000.0

    def __init__(self):
        super().__init__()

        # 使用 double 存储真实世界坐标
        self._world_origin = LPoint3d(0, 0, 0)  # 当前渲染原点（世界坐标）
        self._player_world_pos = LPoint3d(0, 0, 0)  # 玩家真实世界坐标

        # 场景中的物体（使用相对坐标）
        self._world_objects = {}  # {name: world_pos_double}

        # 创建一些远处的物体
        self._create_world_objects()

        # 玩家节点（始终在渲染原点附近）
        self.player = self.render.attachNewNode("player")
        self.player.setPos(0, 0, 0)

        # 模拟玩家移动
        self._move_speed = 100.0  # 100 m/s
        self.taskMgr.add(self._update, "Update")

        # 调试信息
        self.taskMgr.add(self._print_debug, "Debug")

    def _create_world_objects(self):
        """创建分布在大世界中的物体"""
        import random
        rng = random.Random(42)

        for i in range(20):
            # 物体分布在 0-50km 范围内
            x = rng.uniform(-50000, 50000)
            y = rng.uniform(-50000, 50000)
            world_pos = LPoint3d(x, y, 0)
            name = f"object_{i}"
            self._world_objects[name] = world_pos

            # 创建场景节点（使用相对坐标）
            node = self.loader.loadModel("models/environment")
            if node:
                node.reparentTo(self.render)
                node.setName(name)
                # 初始相对坐标
                rel_pos = world_pos - self._world_origin
                node.setPos(rel_pos.x, rel_pos.y, rel_pos.z)

    def _update(self, task):
        """每帧更新：移动玩家，检查是否需要重置原点"""
        dt = globalClock.getDt()

        # 模拟玩家移动（使用 double 精度）
        t = task.time
        self._player_world_pos = LPoint3d(
            math.cos(t * 0.1) * 30000,  # 在 30km 半径圆上移动
            math.sin(t * 0.1) * 30000,
            0
        )

        # 计算玩家相对于渲染原点的位置
        player_rel = self._player_world_pos - self._world_origin
        player_rel_f = LPoint3(player_rel.x, player_rel.y, player_rel.z)

        # 检查是否需要重置原点
        if player_rel_f.length() > self.ORIGIN_RESET_THRESHOLD:
            self._reset_origin()
        else:
            # 更新玩家节点位置（float 精度，但值很小）
            self.player.setPos(player_rel_f)

        return Task.cont

    def _reset_origin(self):
        """
        浮点原点重置：
        将渲染原点移动到玩家当前位置
        所有物体坐标相应调整
        """
        # 新的渲染原点 = 玩家当前世界坐标
        new_origin = LPoint3d(
            self._player_world_pos.x,
            self._player_world_pos.y,
            self._player_world_pos.z
        )

        print(f"重置渲染原点: {self._world_origin} → {new_origin}")
        self._world_origin = new_origin

        # 更新所有物体的相对坐标
        for name, world_pos in self._world_objects.items():
            node = self.render.find(name)
            if node and not node.isEmpty():
                rel_pos = world_pos - self._world_origin
                # 使用 float 设置（此时值已经很小，精度足够）
                node.setPos(rel_pos.x, rel_pos.y, rel_pos.z)

        # 玩家现在在原点
        self.player.setPos(0, 0, 0)

    def _print_debug(self, task):
        """每5秒打印调试信息"""
        if int(task.time) % 5 == 0 and task.time > 0:
            player_rel = self._player_world_pos - self._world_origin
            print(f"玩家世界坐标: ({self._player_world_pos.x:.1f}, {self._player_world_pos.y:.1f})")
            print(f"渲染原点: ({self._world_origin.x:.1f}, {self._world_origin.y:.1f})")
            print(f"玩家渲染坐标: ({player_rel.x:.3f}, {player_rel.y:.3f})")
            print(f"float 精度误差: ~{abs(player_rel.x) * 1.2e-7:.4f}m")
        return Task.cont
```

### 5.3 Python：四元数精度维护

```python
"""
四元数精度问题与解决方案
"""
from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from panda3d.core import LQuaternion, LVecBase3, NodePath
import math

class QuaternionPrecisionDemo(ShowBase):
    def __init__(self):
        super().__init__()

        self.model = self.loader.loadModel("models/environment")
        self.model.reparentTo(self.render)

        # 累积旋转四元数（会产生误差）
        self._accumulated_quat = LQuaternion(1, 0, 0, 0)  # 单位四元数
        self._frame_count = 0

        self.taskMgr.add(self._rotate_with_drift, "RotateWithDrift")

    def _rotate_with_drift(self, task):
        """演示四元数累积误差"""
        dt = globalClock.getDt()
        self._frame_count += 1

        # 每帧旋转一小角度
        angle_per_frame = 1.0  # 度
        delta_quat = LQuaternion()
        delta_quat.setFromAxisAngle(angle_per_frame, LVecBase3(0, 0, 1))

        # 累积旋转（会产生误差）
        self._accumulated_quat = self._accumulated_quat * delta_quat

        # 检查归一化误差
        length = self._accumulated_quat.length()
        if abs(length - 1.0) > 1e-6:
            print(f"帧 {self._frame_count}: 四元数长度 = {length:.8f}（误差: {length-1:.2e}）")

        # ── 解决方案：定期归一化 ──────────────────────────────────────────────
        # 每 100 帧归一化一次（或每帧，取决于精度要求）
        if self._frame_count % 100 == 0:
            self._accumulated_quat.normalize()
            print(f"帧 {self._frame_count}: 已归一化，长度 = {self._accumulated_quat.length():.8f}")

        # 应用旋转
        self.model.setQuat(self._accumulated_quat)

        return Task.cont

    def _safe_slerp(self, q1, q2, t):
        """
        数值稳定的 SLERP 实现
        处理 q1 ≈ q2 和 q1 ≈ -q2 的边界情况
        """
        # 确保两个四元数都已归一化
        q1_norm = LQuaternion(q1)
        q2_norm = LQuaternion(q2)
        q1_norm.normalize()
        q2_norm.normalize()

        # 计算点积
        dot = (q1_norm.getR() * q2_norm.getR() +
               q1_norm.getI() * q2_norm.getI() +
               q1_norm.getJ() * q2_norm.getJ() +
               q1_norm.getK() * q2_norm.getK())

        # 如果点积为负，翻转一个四元数（选择最短路径）
        if dot < 0:
            q2_norm = LQuaternion(-q2_norm.getR(), -q2_norm.getI(),
                                   -q2_norm.getJ(), -q2_norm.getK())
            dot = -dot

        # 如果两个四元数非常接近，使用线性插值（避免除零）
        DOT_THRESHOLD = 0.9995
        if dot > DOT_THRESHOLD:
            # 线性插值 + 归一化
            result = LQuaternion(
                q1_norm.getR() + t * (q2_norm.getR() - q1_norm.getR()),
                q1_norm.getI() + t * (q2_norm.getI() - q1_norm.getI()),
                q1_norm.getJ() + t * (q2_norm.getJ() - q1_norm.getJ()),
                q1_norm.getK() + t * (q2_norm.getK() - q1_norm.getK()),
            )
            result.normalize()
            return result

        # 标准 SLERP
        theta_0 = math.acos(dot)
        theta = theta_0 * t
        sin_theta = math.sin(theta)
        sin_theta_0 = math.sin(theta_0)

        s1 = math.cos(theta) - dot * sin_theta / sin_theta_0
        s2 = sin_theta / sin_theta_0

        return LQuaternion(
            s1 * q1_norm.getR() + s2 * q2_norm.getR(),
            s1 * q1_norm.getI() + s2 * q2_norm.getI(),
            s1 * q1_norm.getJ() + s2 * q2_norm.getJ(),
            s1 * q1_norm.getK() + s2 * q2_norm.getK(),
        )
```

### 5.4 Python：深度精度诊断工具

```python
"""
深度精度诊断：计算当前相机设置下的深度精度
"""
import math

def analyze_depth_precision(near, far, depth_bits=24):
    """
    分析给定相机参数下的深度精度

    返回各距离处的最小可分辨深度差（米）
    """
    total_values = 2 ** depth_bits
    print(f"\n=== 深度精度分析 ===")
    print(f"近裁剪面: {near}m, 远裁剪面: {far}m")
    print(f"深度缓冲位数: {depth_bits}位 ({total_values:,} 个值)")
    print(f"深度比 far/near: {far/near:.0f}x")
    print()

    distances = [near, near*2, near*10, near*100, far/10, far/2, far]
    print(f"{'距离(m)':>12} | {'最小可分辨差(mm)':>18} | {'评级':>6}")
    print("-" * 45)

    for d in distances:
        # OpenGL 深度精度公式
        delta_z = (d * d) / (far * near) * (far - near) / total_values * 1000  # mm
        rating = "优秀" if delta_z < 1 else ("良好" if delta_z < 10 else ("一般" if delta_z < 100 else "差"))
        print(f"{d:>12.1f} | {delta_z:>18.4f} | {rating:>6}")

    print()
    print("建议：")
    print(f"  当前精度比: {far/near:.0f}x")
    if far/near > 10000:
        print("  ⚠️  精度比过大，建议减小 far 或增大 near")
    if near < 0.5:
        print("  ⚠️  near 过小，建议设置为 0.5-1.0")
    print()


def recommend_near_far(scene_size_m, player_height_m=1.8):
    """根据场景大小推荐近/远裁剪面"""
    near = player_height_m * 0.1  # 近裁剪面约为玩家高度的 10%
    far = scene_size_m * 1.5      # 远裁剪面覆盖整个场景

    # 确保精度比不超过 10000
    if far / near > 10000:
        near = far / 10000

    print(f"场景大小: {scene_size_m}m")
    print(f"推荐 near: {near:.2f}m")
    print(f"推荐 far: {far:.0f}m")
    return near, far


# 使用示例
if __name__ == "__main__":
    # 分析不同配置的深度精度
    print("=== 配置1：默认设置（常见问题）===")
    analyze_depth_precision(near=0.1, far=10000)

    print("=== 配置2：优化设置 ===")
    analyze_depth_precision(near=1.0, far=5000)

    print("=== 配置3：大世界设置 ===")
    analyze_depth_precision(near=1.0, far=100000, depth_bits=32)

    # 推荐设置
    near, far = recommend_near_far(scene_size_m=1000)
```

### 5.5 GLSL：精度感知 Shader

```glsl
/* 精度感知的 Shader 编写最佳实践 */

/* ── 顶点着色器：避免大数值计算 ─────────────────────────────────────────────── */
#version 330

uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelMatrix;
uniform vec3 camera_world_pos;  // 相机世界坐标（用于大世界）

in vec4 p3d_Vertex;
in vec3 p3d_Normal;

out vec3 world_pos;
out vec3 view_dir;

void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;

    // 世界空间位置
    world_pos = (p3d_ModelMatrix * p3d_Vertex).xyz;

    // 视线方向（相对于相机，避免大数值相减）
    // ❌ 错误：world_pos - camera_world_pos 可能损失精度
    // ✅ 正确：在顶点着色器中计算（精度更高）
    view_dir = normalize(camera_world_pos - world_pos);
}
```

```glsl
/* ── 片段着色器：精度注意事项 ───────────────────────────────────────────────── */
#version 330

in vec3 world_pos;
in vec3 view_dir;

out vec4 fragColor;

/* 数值稳定的菲涅尔计算 */
float fresnel_schlick(float cos_theta, float F0) {
    // 避免 pow(1-cos_theta, 5) 在 cos_theta=1 时的精度问题
    float x = clamp(1.0 - cos_theta, 0.0, 1.0);
    float x2 = x * x;
    return F0 + (1.0 - F0) * x2 * x2 * x;
}

/* 数值稳定的法线贴图解码 */
vec3 decode_normal(vec2 encoded) {
    // BC5/ATI2 格式：只存储 XY，Z 从 X²+Y²+Z²=1 推导
    vec2 xy = encoded * 2.0 - 1.0;
    float z_sq = 1.0 - dot(xy, xy);
    // 使用 max 避免负数开方（精度误差可能导致 z_sq < 0）
    float z = sqrt(max(z_sq, 0.0));
    return normalize(vec3(xy, z));
}

/* 数值稳定的距离衰减 */
float distance_attenuation(float dist, float radius) {
    // 避免除零
    float dist_sq = dist * dist;
    float radius_sq = radius * radius;
    // 平滑截止（避免硬边界）
    float factor = dist_sq / max(radius_sq, 0.0001);
    return max(1.0 - factor, 0.0);
}

void main() {
    vec3 N = normalize(vec3(0, 0, 1));  // 简化示例
    vec3 V = normalize(view_dir);

    float cos_theta = max(dot(N, V), 0.0);
    float fresnel = fresnel_schlick(cos_theta, 0.04);

    fragColor = vec4(vec3(fresnel), 1.0);
}
```

---

## 6. 性能优化

### 6.1 精度 vs 性能权衡

```python
# ── 选择合适的精度级别 ────────────────────────────────────────────────────────

# 场景1：小型游戏（场景 < 1km）
# float 精度完全足够，不需要特殊处理
lens.setNear(0.5)
lens.setFar(1000)

# 场景2：中型游戏（场景 1-10km）
# 调整近裁剪面，使用 24 位深度缓冲
lens.setNear(1.0)
lens.setFar(5000)

# 场景3：大型开放世界（场景 > 10km）
# 需要浮点原点技术
lens.setNear(1.0)
lens.setFar(10000)
# + 实现 FloatingOrigin 系统

# 场景4：天文模拟（场景 > 1000km）
# 需要 double 精度 + 分层坐标系
from panda3d.core import loadPrcFileData
loadPrcFileData("", "stdfloat-double true")  # 全局 double 精度
```

### 6.2 常见精度 Bug 及修复

```python
# ── Bug 1：Z-Fighting ─────────────────────────────────────────────────────────
# 症状：两个重叠面闪烁
# 原因：深度值相同，GPU 随机选择哪个面

# ❌ 错误：两个面完全重叠
decal.setPos(ground.getPos())  # 完全相同位置

# ✅ 修复：使用 DepthOffsetAttrib
from panda3d.core import DepthOffsetAttrib
decal.setAttrib(DepthOffsetAttrib.make(1))

# ── Bug 2：远处物体抖动 ───────────────────────────────────────────────────────
# 症状：距离 > 10km 的物体位置抖动
# 原因：float 精度不足

# ❌ 错误：直接使用大坐标
obj.setPos(50000, 50000, 0)  # float 精度只有 ~5m！

# ✅ 修复：使用浮点原点
# 将渲染原点移到玩家附近，物体使用相对坐标

# ── Bug 3：骨骼动画漂移 ───────────────────────────────────────────────────────
# 症状：长时间运行后骨骼位置偏移
# 原因：四元数累积误差

# ✅ 修复：定期归一化四元数
def update_bone(bone_quat, delta_quat, frame):
    result = bone_quat * delta_quat
    if frame % 60 == 0:  # 每60帧归一化一次
        result.normalize()
    return result

# ── Bug 4：碰撞穿透 ───────────────────────────────────────────────────────────
# 症状：快速移动的物体穿过薄墙
# 原因：碰撞检测精度不足 + 帧率过低

# ✅ 修复：使用 CCD（连续碰撞检测）+ 增加碰撞体厚度
from panda3d.core import CollisionBox, Point3
# 给墙增加足够厚度
wall = CollisionBox(Point3(0,0,0), 10, 0.2, 5)  # 厚度 0.2m 而非 0.01m
```

### 6.3 精度测试工具

```python
def test_float_precision():
    """测试 float 在不同数量级下的精度"""
    import struct

    test_values = [1.0, 10.0, 100.0, 1000.0, 10000.0, 100000.0]

    print("float 精度测试:")
    print(f"{'值':>12} | {'最小增量':>15} | {'相对误差':>12}")
    print("-" * 45)

    for v in test_values:
        # 找到 float 能表示的下一个值
        bits = struct.unpack('I', struct.pack('f', v))[0]
        next_bits = bits + 1
        next_v = struct.unpack('f', struct.pack('I', next_bits))[0]
        delta = next_v - v
        relative = delta / v

        print(f"{v:>12.0f} | {delta:>15.8f} | {relative:>12.2e}")

    print()
    print("结论：")
    print("  在 10000m 处，float 最小增量约 0.001m（1mm）")
    print("  在 100000m 处，float 最小增量约 0.01m（1cm）")
    print("  超过 100km 时，float 精度不足以表示厘米级差异")


if __name__ == "__main__":
    test_float_precision()
```

---

## 小结

| 知识点 | 核心要点 |
|--------|----------|
| **IEEE 754** | float 约 7 位有效数字，相对精度 $\approx 10^{-7}$ |
| **Z-Fighting** | 深度精度 $\propto z^2$，远处精度极低；增大 near 是最有效解决方案 |
| **DepthOffsetAttrib** | 为重叠几何体添加深度偏移，解决 Z-Fighting |
| **大世界精度** | 坐标 > 10km 时 float 精度不足；使用浮点原点技术 |
| **四元数漂移** | 累积旋转后需定期归一化；SLERP 需处理边界情况 |
| **PN_stdfloat** | Panda3D 可配置精度类型，`stdfloat-double true` 启用 double |
| **深度比** | `far/near` 比值越大，深度精度越差；建议 < 10000 |
| **碰撞精度** | 碰撞体不能太薄；快速物体需要 CCD |

### 精度问题诊断流程

```
症状：物体闪烁/抖动
  ├── 近处闪烁 → Z-Fighting → DepthOffsetAttrib + 调整 near
  ├── 远处抖动 → 大世界精度 → 浮点原点技术
  ├── 动画漂移 → 四元数误差 → 定期归一化
  └── 碰撞穿透 → 碰撞精度 → 增加厚度 + CCD
```

### 关键设计原则

1. **近裁剪面是深度精度的关键**：`near` 从 0.1 改为 1.0，精度提升 10 倍
2. **大世界必须用浮点原点**：游戏逻辑用 double，渲染用相对坐标
3. **四元数要定期归一化**：每 60-100 帧归一化一次
4. **碰撞体要有足够厚度**：最薄不应小于 0.1m
5. **Shader 中避免大数相减**：在顶点着色器中计算，精度更高

### 与其他专题的关联

- **专题03（变换系统）**：矩阵累积误差与四元数漂移
- **专题07（碰撞检测）**：碰撞精度直接影响物理模拟稳定性
- **专题11（后处理）**：深度缓冲精度影响 SSAO、景深等效果
- **专题13（跨平台）**：不同平台的深度范围（[-1,1] vs [0,1]）影响精度分布
