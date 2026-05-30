# 专题03：变换系统与坐标空间

## 目录
1. [问题背景](#1-问题背景)
2. [数学原理](#2-数学原理)
   - 2.1 仿射变换与齐次坐标
   - 2.2 TRS 分解：位置、旋转、缩放
   - 2.3 四元数旋转
   - 2.4 坐标系约定与转换
   - 2.5 变换复合的代数性质
3. [工程实践](#3-工程实践)
   - 3.1 双重表示：组件式 vs 矩阵式
   - 3.2 懒惰计算与标志位系统
   - 3.3 全局缓存（Flyweight 模式）
   - 3.4 坐标系统一
4. [Panda3D 源码解析](#4-panda3d-源码解析)
   - 4.1 TransformState 类结构
   - 4.2 do_compose() — 变换复合
   - 4.3 do_calc_mat() — 组件转矩阵
   - 4.4 do_calc_components() — 矩阵分解
5. [代码演示](#5-代码演示)
6. [性能分析](#6-性能分析)

---

## 1. 问题背景

3D 引擎中的变换系统需要解决以下核心问题：

1. **表示问题**：如何存储一个物体的位置、旋转、缩放？
2. **复合问题**：父子节点的变换如何合并为世界变换？
3. **坐标系问题**：不同系统（物理引擎、动画系统、渲染器）使用不同坐标系约定，如何统一？
4. **性能问题**：矩阵乘法代价高，如何避免重复计算？

Panda3D 的 [`TransformState`](../../panda/src/pgraph/transformState.h) 类是这些问题的核心解决方案。

---

## 2. 数学原理

### 2.1 仿射变换与齐次坐标

3D 变换（平移、旋转、缩放）统一用 **4×4 齐次矩阵** 表示：

$$M = \begin{pmatrix} R_{3\times3} & \mathbf{t} \\ \mathbf{0}^T & 1 \end{pmatrix}$$

其中 $R_{3\times3}$ 是旋转+缩放矩阵，$\mathbf{t}$ 是平移向量。

**齐次坐标**：3D 点 $(x, y, z)$ 表示为 $(x, y, z, 1)$，方向向量表示为 $(x, y, z, 0)$。

变换点：
$$\begin{pmatrix} x' \\ y' \\ z' \\ 1 \end{pmatrix} = M \begin{pmatrix} x \\ y \\ z \\ 1 \end{pmatrix}$$

变换方向（不受平移影响）：
$$\begin{pmatrix} x' \\ y' \\ z' \\ 0 \end{pmatrix} = M \begin{pmatrix} x \\ y \\ z \\ 0 \end{pmatrix}$$

### 2.2 TRS 分解：位置、旋转、缩放

标准 TRS 矩阵分解：

$$M_{TRS} = T \cdot R \cdot S$$

其中：
- $T$：平移矩阵 $\begin{pmatrix} I & \mathbf{t} \\ 0 & 1 \end{pmatrix}$
- $R$：旋转矩阵（正交矩阵，$R^T = R^{-1}$）
- $S$：缩放矩阵 $\text{diag}(s_x, s_y, s_z, 1)$

**展开形式**：

$$M_{TRS} = \begin{pmatrix}
s_x r_{00} & s_y r_{01} & s_z r_{02} & t_x \\
s_x r_{10} & s_y r_{11} & s_z r_{12} & t_y \\
s_x r_{20} & s_y r_{21} & s_z r_{22} & t_z \\
0 & 0 & 0 & 1
\end{pmatrix}$$

**矩阵分解（Decompose）**：给定矩阵 $M$，提取 TRS 分量：

1. 提取缩放：$s_i = \|\text{column}_i(M_{3\times3})\|$
2. 提取旋转：$R = M_{3\times3} \cdot \text{diag}(1/s_x, 1/s_y, 1/s_z)$
3. 提取平移：直接读取第4列

**注意**：非均匀缩放（$s_x \neq s_y \neq s_z$）与旋转的复合会产生剪切（Shear），使分解变得复杂。

### 2.3 四元数旋转

**四元数** $q = w + xi + yj + zk$，其中 $i^2 = j^2 = k^2 = ijk = -1$。

单位四元数（$|q| = 1$）表示旋转：绕轴 $\hat{n}$ 旋转角度 $\theta$：

$$q = \cos\frac{\theta}{2} + \sin\frac{\theta}{2}(n_x i + n_y j + n_z k)$$

**四元数复合**（旋转叠加）：

$$q_{AB} = q_B \cdot q_A$$

注意顺序：先应用 $q_A$，再应用 $q_B$，结果是 $q_B \cdot q_A$（右乘）。

**四元数 vs 欧拉角（HPR）**：

| 特性 | 四元数 | 欧拉角（HPR） |
|------|--------|--------------|
| 存储 | 4 floats | 3 floats |
| 插值 | SLERP（平滑） | 线性（可能万向锁） |
| 万向锁 | 无 | 有 |
| 直觉性 | 低 | 高 |
| 复合代价 | O(1) | 需转换为矩阵 |

Panda3D 内部优先使用四元数，但提供 HPR 接口供用户使用。

**HPR 约定**（Panda3D 特有）：
- **H**（Heading）：绕 Z 轴旋转（偏航，Yaw）
- **P**（Pitch）：绕 Y 轴旋转（俯仰）
- **R**（Roll）：绕 X 轴旋转（翻滚）
- 应用顺序：H → P → R（ZYX 欧拉角）

### 2.4 坐标系约定与转换

不同系统使用不同的坐标系约定：

| 系统 | 右手/左手 | 上方向 | 前方向 |
|------|----------|--------|--------|
| Panda3D | 右手 | Z 轴向上 | Y 轴向前 |
| OpenGL | 右手 | Y 轴向上 | -Z 轴向前 |
| DirectX | 左手 | Y 轴向上 | Z 轴向前 |
| Blender | 右手 | Z 轴向上 | -Y 轴向前 |
| Unity | 左手 | Y 轴向上 | Z 轴向前 |

**坐标系转换矩阵**（Panda3D → OpenGL）：

$$M_{P3D \to GL} = \begin{pmatrix}
1 & 0 & 0 & 0 \\
0 & 0 & -1 & 0 \\
0 & 1 & 0 & 0 \\
0 & 0 & 0 & 1
\end{pmatrix}$$

即：$x_{GL} = x_{P3D}$，$y_{GL} = -z_{P3D}$，$z_{GL} = y_{P3D}$

Panda3D 在 GSG 层自动处理这个转换，用户无需手动处理。

### 2.5 变换复合的代数性质

**变换复合**（父变换 $P$，子变换 $C$）：

$$M_{world} = M_P \cdot M_C$$

**均匀缩放时的快速复合**（Panda3D 优化）：

当父变换有均匀缩放 $s$，子变换有位置 $\mathbf{p}_C$、四元数 $q_C$、缩放 $s_C$ 时：

$$\mathbf{p}_{world} = \mathbf{p}_P + q_P \cdot (\mathbf{p}_C \cdot s_P)$$
$$q_{world} = q_C \cdot q_P$$
$$s_{world} = s_C \cdot s_P$$

这比完整的矩阵乘法（64次乘法+48次加法）快得多。

**逆变换**（用于视图矩阵）：

$$M^{-1}_{TRS} = S^{-1} \cdot R^{-1} \cdot T^{-1} = S^{-1} \cdot R^T \cdot T^{-1}$$

---

## 3. 工程实践

### 3.1 双重表示：组件式 vs 矩阵式

`TransformState` 同时支持两种表示方式：

```
创建方式 1：组件式（用户友好）
  make_pos_hpr_scale(pos, hpr, scale)
  → 存储 _pos, _hpr/_quat, _scale
  → 矩阵按需计算（懒惰）

创建方式 2：矩阵式（精确控制）
  make_mat(matrix)
  → 存储 _mat
  → 组件按需分解（懒惰）
```

**优势**：
- 组件式：避免矩阵分解的精度损失，支持快速组件复合
- 矩阵式：支持任意仿射变换（包括剪切）

### 3.2 懒惰计算与标志位系统

`TransformState` 使用位标志（`_flags`）跟踪哪些表示已计算：

```cpp
// transformState.h 中的标志位（简化）
enum Flags {
  F_is_identity       = 0x00001,  // 是否为单位变换
  F_is_invalid        = 0x00002,  // 是否无效（奇异矩阵）
  F_components_given  = 0x00004,  // 是否以组件方式创建
  F_components_known  = 0x00008,  // 组件是否已计算
  F_has_components    = 0x00010,  // 是否有有效组件
  F_mat_known         = 0x00020,  // 矩阵是否已计算
  F_hpr_given         = 0x00040,  // 是否以 HPR 方式创建
  F_hpr_known         = 0x00080,  // HPR 是否已计算
  F_quat_given        = 0x00100,  // 是否以四元数方式创建
  F_quat_known        = 0x00200,  // 四元数是否已计算
  F_singular_known    = 0x00400,  // 是否已检测奇异性
  F_is_singular       = 0x00800,  // 是否为奇异矩阵
  F_uniform_scale     = 0x01000,  // 是否均匀缩放
  F_identity_scale    = 0x02000,  // 缩放是否为 1
  F_is_2d             = 0x04000,  // 是否为 2D 变换
};
```

**懒惰计算流程**：

```
get_mat() 被调用
    ↓
检查 F_mat_known 标志
    ↓ 未设置
do_calc_mat()
    ↓
检查 F_hpr_known
    ↓ 未设置
do_calc_hpr()  ← 从四元数转换
    ↓
compose_matrix(_mat, _scale, _shear, _hpr, _pos)
    ↓
设置 F_mat_known 标志
```

### 3.3 全局缓存（Flyweight 模式）

与 `RenderState` 相同，`TransformState` 也使用全局哈希表缓存所有实例：

```cpp
// 全局缓存：相同变换只存一份
static States _states;  // unordered_set<TransformState*>

static CPT(TransformState) return_new(TransformState *state) {
  // 在全局缓存中查找等价的已有状态
  auto si = _states.find(state);
  if (si != _states.end()) {
    delete state;
    return *si;  // 返回已有实例
  }
  _states.insert(state);
  return state;
}
```

**复合缓存**：每个 `TransformState` 还维护一个局部复合缓存：

```cpp
// 记录 this->compose(other) 的结果
typedef SimpleHashMap<const TransformState*, const TransformState*> CompositionCache;
CompositionCache _composition_cache;
CompositionCache _invert_composition_cache;
```

### 3.4 坐标系统一

Panda3D 在不同层次处理坐标系转换：

```
用户代码（Panda3D 坐标系：Z-up, Y-forward）
    ↓
NodePath.set_pos() / set_hpr()
    ↓
TransformState（Panda3D 坐标系）
    ↓
GSG.set_state_and_transform()
    ↓
cs_transform（坐标系转换矩阵）
    ↓
OpenGL/DirectX（各自的坐标系）
```

---

## 4. Panda3D 源码解析

### 4.1 TransformState 类结构

**文件**：[`panda/src/pgraph/transformState.h`](../../panda/src/pgraph/transformState.h)

```cpp
// transformState.h:54
class EXPCL_PANDA_PGRAPH TransformState final
    : public NodeCachedReferenceCount {

  // ── 工厂方法（静态，返回全局唯一实例）──────────────────────────
  static CPT(TransformState) make_identity();
  static CPT(TransformState) make_pos(const LVecBase3 &pos);
  static CPT(TransformState) make_hpr(const LVecBase3 &hpr);
  static CPT(TransformState) make_quat(const LQuaternion &quat);
  static CPT(TransformState) make_pos_hpr_scale(
      const LVecBase3 &pos, const LVecBase3 &hpr, const LVecBase3 &scale);
  static CPT(TransformState) make_mat(const LMatrix4 &mat);

  // ── 查询方法（懒惰计算）────────────────────────────────────────
  bool is_identity() const;
  bool has_components() const;   // 是否有有效的 TRS 分量
  bool has_uniform_scale() const;
  const LPoint3 &get_pos() const;
  const LVecBase3 &get_hpr() const;
  const LQuaternion &get_quat() const;
  const LVecBase3 &get_scale() const;
  const LMatrix4 &get_mat() const;
  const LMatrix4 *get_inverse_mat() const;  // 可能返回 nullptr（奇异矩阵）

  // ── 变换操作（返回新实例，不修改自身）──────────────────────────
  CPT(TransformState) compose(const TransformState *other) const;
  CPT(TransformState) invert_compose(const TransformState *other) const;
  CPT(TransformState) get_inverse() const;

  // ── 修改方法（返回新实例）──────────────────────────────────────
  CPT(TransformState) set_pos(const LVecBase3 &pos) const;
  CPT(TransformState) set_hpr(const LVecBase3 &hpr) const;
  CPT(TransformState) set_scale(const LVecBase3 &scale) const;

private:
  // 内部存储（双重表示）
  mutable LPoint3 _pos;
  mutable LVecBase3 _hpr;
  mutable LQuaternion _quat, _norm_quat;
  mutable LVecBase3 _scale, _shear;
  mutable LMatrix4 _mat;
  mutable LMatrix4 *_inv_mat;  // 按需计算的逆矩阵

  mutable int _flags;  // 标志位，跟踪哪些表示已计算
  mutable LightMutex _lock;  // 线程安全锁

  // 复合缓存
  CompositionCache _composition_cache;
  CompositionCache _invert_composition_cache;
};
```

### 4.2 do_compose() — 变换复合

**文件**：[`panda/src/pgraph/transformState.cxx:1513`](../../panda/src/pgraph/transformState.cxx)

```cpp
CPT(TransformState) TransformState::
do_compose(const TransformState *other) const {
  PStatTimer timer(_transform_compose_pcollector);

  // ── 快速路径：组件式复合（均匀缩放，无剪切）──────────────────
  if (compose_componentwise &&
      has_uniform_scale() &&
      !has_nonzero_shear() && !other->has_nonzero_shear() &&
      ((components_given() && other->has_components()) ||
       (other->components_given() && has_components()))) {

    // 3D 组件式复合
    LVecBase3 pos = get_pos();
    LQuaternion quat = get_norm_quat();
    PN_stdfloat scale = get_uniform_scale();

    // 关键公式：子节点位置需要经过父节点的旋转和缩放变换
    // p_world = p_parent + q_parent.rotate(p_child * scale_parent)
    pos += quat.xform(other->get_pos()) * scale;

    // 旋转复合：q_world = q_child * q_parent（注意顺序）
    quat = other->get_norm_quat() * quat;

    // 缩放复合：s_world = s_child * s_parent
    LVecBase3 new_scale = other->get_scale() * scale;

    return make_pos_quat_scale(pos, quat, new_scale);
  }

  // ── 慢速路径：矩阵乘法 ────────────────────────────────────────
  // new_mat = other->mat * this->mat
  // （Panda3D 使用行向量，所以是右乘）
  LMatrix4 new_mat;
  new_mat.multiply(other->get_mat(), get_mat());
  return make_mat(new_mat);
}
```

**关键设计**：
- 优先使用组件式复合（避免矩阵分解的精度损失）
- 条件：均匀缩放 + 无剪切 + 至少一方以组件方式创建
- 退化到矩阵乘法处理一般情况

### 4.3 do_calc_mat() — 组件转矩阵

```cpp
// transformState.cxx:2216
void TransformState::
do_calc_mat() {
  if ((_flags & F_mat_known) != 0) {
    return;  // 已计算，直接返回
  }

  // 确保 HPR 已知（可能需要从四元数转换）
  if ((_flags & F_hpr_known) == 0) {
    do_calc_hpr();
  }

  // 调用数学库函数：TRS → 矩阵
  // compose_matrix(mat, scale, shear, hpr, pos)
  compose_matrix(_mat, _scale, _shear, get_hpr(), _pos);

  _flags |= F_mat_known;
}
```

[`compose_matrix()`](../../panda/src/mathutil/fftCompressor.cxx) 的数学实现：

```
M = T(pos) * R(hpr) * S(scale) * Sh(shear)

其中 R(hpr) = R_H * R_P * R_R
  R_H = 绕 Z 轴旋转 H 度
  R_P = 绕 Y 轴旋转 P 度
  R_R = 绕 X 轴旋转 R 度
```

### 4.4 do_calc_components() — 矩阵分解

```cpp
// transformState.cxx:2111
void TransformState::
do_calc_components() {
  if ((_flags & F_components_known) != 0) {
    return;  // 已计算
  }

  // 必须已有矩阵
  nassertv((_flags & F_mat_known) != 0);

  // 调用矩阵分解函数
  // decompose_matrix(mat, scale, shear, hpr, pos)
  bool possible = decompose_matrix(_mat, _scale, _shear, _hpr, _pos);

  if (!possible) {
    // 矩阵无法分解（如零缩放）
    // 存储近似值，但不设置 F_has_components
    _flags |= F_components_known | F_hpr_known;
  } else {
    // 分解成功
    _flags |= F_has_components | F_components_known | F_hpr_known;
    check_uniform_scale();  // 检查是否均匀缩放
  }
}
```

**矩阵分解算法**（`decompose_matrix`）：

```
输入：4×4 矩阵 M
输出：pos, scale, shear, hpr

1. 提取平移：pos = M[3][0..2]

2. 提取上3×3子矩阵 R'（包含旋转和缩放）

3. 提取缩放（列向量的模）：
   scale.x = |R'[col0]|
   scale.y = |R'[col1]|
   scale.z = |R'[col2]|

4. 归一化得到纯旋转矩阵 R：
   R = R' * diag(1/scale.x, 1/scale.y, 1/scale.z)

5. 提取剪切（非对角元素）

6. 从旋转矩阵提取 HPR（欧拉角）：
   P = asin(-R[2][0])
   H = atan2(R[1][0], R[0][0])
   R_angle = atan2(R[2][1], R[2][2])
```

---

## 5. 代码演示

### 5.1 Python：基本变换操作

```python
from panda3d.core import NodePath, TransformState, LPoint3, LVecBase3, LQuaternion

# ── NodePath 高层接口 ────────────────────────────────────────────────────────
node = NodePath("my_node")

# 设置位置（局部坐标）
node.set_pos(10, 20, 5)
node.set_x(10)  # 只设置 X 分量

# 设置旋转（HPR：Heading, Pitch, Roll，单位：度）
node.set_hpr(45, 0, 0)   # 绕 Z 轴旋转 45 度
node.set_h(45)            # 只设置 Heading

# 设置缩放
node.set_scale(2.0)       # 均匀缩放
node.set_scale(2, 1, 0.5) # 非均匀缩放

# 组合设置
node.set_pos_hpr_scale(
    LPoint3(10, 20, 5),
    LVecBase3(45, 0, 0),
    LVecBase3(1, 1, 1)
)

# ── 世界坐标 vs 局部坐标 ────────────────────────────────────────────────────
parent = NodePath("parent")
parent.set_pos(100, 0, 0)
child = parent.attach_new_node("child")
child.set_pos(10, 0, 0)  # 局部坐标

# 获取世界坐标
world_pos = child.get_pos(render)  # (110, 0, 0)
print(f"World pos: {world_pos}")

# 在不同坐标系间转换
local_pos = child.get_pos(parent)  # (10, 0, 0)
print(f"Local pos: {local_pos}")

# ── 直接操作 TransformState ──────────────────────────────────────────────────
# 创建变换状态
ts1 = TransformState.make_pos(LPoint3(10, 0, 0))
ts2 = TransformState.make_hpr(LVecBase3(45, 0, 0))
ts3 = TransformState.make_scale(2.0)

# 复合变换（先缩放，再旋转，再平移）
combined = ts1.compose(ts2.compose(ts3))
print(f"Combined matrix:\n{combined.get_mat()}")

# 获取逆变换
inverse = combined.get_inverse()
print(f"Is identity after compose with inverse: "
      f"{combined.compose(inverse).is_identity()}")
```

### 5.2 Python：四元数操作

```python
from panda3d.core import LQuaternion, LVecBase3, LPoint3, TransformState
import math

# ── 四元数基本操作 ───────────────────────────────────────────────────────────
# 绕 Z 轴旋转 90 度
q1 = LQuaternion()
q1.set_from_axis_angle(90, LVecBase3(0, 0, 1))

# 绕 X 轴旋转 45 度
q2 = LQuaternion()
q2.set_from_axis_angle(45, LVecBase3(1, 0, 0))

# 复合旋转（先 q1，再 q2）
q_combined = q2 * q1  # 注意：右乘表示先应用 q1

# 旋转一个向量
v = LVecBase3(0, 1, 0)  # Y 轴方向
v_rotated = q1.xform(v)
print(f"Rotated: {v_rotated}")  # 应该接近 (-1, 0, 0)

# ── SLERP 插值（动画中常用）─────────────────────────────────────────────────
q_start = LQuaternion()
q_start.set_from_axis_angle(0, LVecBase3(0, 0, 1))

q_end = LQuaternion()
q_end.set_from_axis_angle(180, LVecBase3(0, 0, 1))

# 在 0 到 1 之间插值
t = 0.5
q_mid = LQuaternion()
q_mid.slerp(q_start, q_end, t)
print(f"SLERP at t=0.5: {q_mid.get_hpr()}")  # 应该接近 (90, 0, 0)

# ── HPR 与四元数转换 ─────────────────────────────────────────────────────────
hpr = LVecBase3(45, 30, 0)
q = LQuaternion()
q.set_hpr(hpr)
print(f"HPR to Quat: {q}")

# 反向转换
hpr_back = q.get_hpr()
print(f"Quat to HPR: {hpr_back}")  # 应该接近原始 HPR
```

### 5.3 Python：坐标系转换

```python
from panda3d.core import NodePath, LPoint3, LVecBase3

# ── 在不同节点坐标系间转换 ──────────────────────────────────────────────────
# 场景结构：
#   world
#   └── room (pos=100,0,0, hpr=45,0,0)
#       └── table (pos=0,5,0)
#           └── cup (pos=0,0,1)

world = render
room = world.attach_new_node("room")
room.set_pos(100, 0, 0)
room.set_h(45)  # 旋转 45 度

table = room.attach_new_node("table")
table.set_pos(0, 5, 0)

cup = table.attach_new_node("cup")
cup.set_pos(0, 0, 1)

# 获取 cup 在不同坐标系中的位置
cup_world = cup.get_pos(world)    # 世界坐标
cup_room  = cup.get_pos(room)     # 相对于 room 的坐标
cup_table = cup.get_pos(table)    # 相对于 table 的坐标（即局部坐标）

print(f"Cup in world: {cup_world}")
print(f"Cup in room:  {cup_room}")
print(f"Cup in table: {cup_table}")

# ── 将世界坐标转换为局部坐标 ────────────────────────────────────────────────
world_point = LPoint3(110, 5, 1)
local_point = room.get_relative_point(world, world_point)
print(f"World {world_point} → Room local: {local_point}")

# ── 对齐到另一个节点 ─────────────────────────────────────────────────────────
# 将 cup 的变换设置为与另一个节点相同
target = NodePath("target")
target.set_pos_hpr(50, 50, 0, 90, 0, 0)
cup.set_transform(target.get_transform(world))
```

### 5.4 Python：变换插值（动画过渡）

```python
from panda3d.core import LPoint3, LVecBase3, LQuaternion, TransformState
from direct.interval.LerpInterval import LerpPosHprInterval

# ── 使用 Interval 系统进行平滑过渡 ──────────────────────────────────────────
node = NodePath("animated_node")
node.reparent_to(render)

# 位置插值（线性）
pos_interval = node.posInterval(
    duration=2.0,
    pos=LPoint3(100, 0, 0),
    startPos=LPoint3(0, 0, 0)
)

# HPR 插值（线性，可能有万向锁问题）
hpr_interval = node.hprInterval(
    duration=2.0,
    hpr=LVecBase3(180, 0, 0),
    startHpr=LVecBase3(0, 0, 0)
)

# 四元数插值（SLERP，更平滑）
quat_interval = node.quatInterval(
    duration=2.0,
    quat=LQuaternion(),  # 目标四元数
    startQuat=LQuaternion()  # 起始四元数
)

# ── 手动 SLERP 插值 ──────────────────────────────────────────────────────────
def lerp_transform(ts_start: TransformState, ts_end: TransformState, t: float):
    """在两个变换状态之间插值"""
    # 位置线性插值
    pos = ts_start.get_pos() + (ts_end.get_pos() - ts_start.get_pos()) * t

    # 旋转 SLERP 插值
    q_start = ts_start.get_norm_quat()
    q_end = ts_end.get_norm_quat()
    q_interp = LQuaternion()
    q_interp.slerp(q_start, q_end, t)

    # 缩放线性插值
    scale = ts_start.get_scale() + (ts_end.get_scale() - ts_start.get_scale()) * t

    return TransformState.make_pos_quat_scale(pos, q_interp, scale)
```

### 5.5 C++：自定义变换操作

```cpp
#include "transformState.h"
#include "nodePath.h"

// 计算两个节点之间的相对变换
CPT(TransformState) get_relative_transform(
    const NodePath &from, const NodePath &to) {

  // from 的世界变换
  CPT(TransformState) from_world = from.get_net_transform();
  // to 的世界变换
  CPT(TransformState) to_world = to.get_net_transform();

  // 相对变换 = from_world^(-1) * to_world
  // 即：先撤销 from 的变换，再应用 to 的变换
  return from_world->invert_compose(to_world);
}

// 在局部空间中旋转节点（绕世界轴旋转）
void rotate_around_world_axis(NodePath &node,
                               const LVecBase3 &world_axis,
                               float angle_deg) {
  // 将世界轴转换到节点的局部空间
  NodePath parent = node.get_parent();
  LVecBase3 local_axis = parent.get_relative_vector(render, world_axis);

  // 在局部空间中旋转
  LQuaternion q;
  q.set_from_axis_angle(angle_deg, local_axis);

  // 复合到当前旋转
  LQuaternion current_q = node.get_quat();
  node.set_quat(q * current_q);
}
```

---

## 6. 性能分析

### 6.1 变换操作代价对比

| 操作 | 代价 | 说明 |
|------|------|------|
| `make_identity()` | O(1) | 返回全局单例 |
| `make_pos(pos)` | O(1) | 哈希查找 |
| `compose()` — 组件式 | ~20 ops | 四元数乘法 + 向量运算 |
| `compose()` — 矩阵式 | ~64 muls | 4×4 矩阵乘法 |
| `get_mat()` — 已缓存 | O(1) | 直接返回 |
| `get_mat()` — 未缓存 | ~50 ops | `compose_matrix()` |
| `get_hpr()` — 未缓存 | ~100 ops | 矩阵分解 |
| `get_inverse_mat()` | ~100 ops | 高斯消元 |

### 6.2 常见性能陷阱

```python
# ❌ 错误：频繁调用 get_hpr()（触发矩阵分解）
for i in range(1000):
    node.set_mat(some_matrix)  # 矩阵方式设置
    hpr = node.get_hpr()       # 每次都触发矩阵分解！

# ✅ 正确：如果需要 HPR，直接用 HPR 方式设置
for i in range(1000):
    node.set_hpr(some_hpr)     # 组件方式设置，HPR 直接可用
    hpr = node.get_hpr()       # 直接返回，无需分解

# ❌ 错误：非均匀缩放 + 旋转（强制走矩阵路径）
node.set_scale(2, 1, 0.5)  # 非均匀缩放
node.set_hpr(45, 0, 0)     # 旋转
# compose() 无法走快速路径，必须用矩阵乘法

# ✅ 正确：尽量使用均匀缩放
node.set_scale(2.0)         # 均匀缩放
node.set_hpr(45, 0, 0)     # compose() 可以走快速路径

# ❌ 错误：每帧重新创建 TransformState
def update(dt):
    ts = TransformState.make_pos(LPoint3(x, y, z))  # 每帧创建新对象
    node.set_transform(ts)

# ✅ 正确：直接使用 NodePath 接口（内部优化）
def update(dt):
    node.set_pos(x, y, z)  # 内部高效处理
```

### 6.3 坐标系转换代价

```python
# get_pos(other_node) 的内部实现：
# 1. 计算 self 的世界变换（可能触发 update_cached）
# 2. 计算 other_node 的世界变换（可能触发 update_cached）
# 3. 计算相对变换：world_self * inverse(world_other)
# 代价：O(depth_self + depth_other)

# 优化：缓存频繁使用的相对变换
class CachedRelativePos:
    def __init__(self, node, reference):
        self.node = node
        self.reference = reference
        self._cached_pos = None
        self._last_transform_seq = -1

    def get(self):
        # 检查变换是否改变（通过序列号）
        current_seq = self.node.get_transform().get_hash()
        if current_seq != self._last_transform_seq:
            self._cached_pos = self.node.get_pos(self.reference)
            self._last_transform_seq = current_seq
        return self._cached_pos
```

---

## 小结

| 概念 | 核心思想 | Panda3D 实现 |
|------|----------|-------------|
| 齐次坐标 | 统一平移/旋转/缩放为矩阵乘法 | `LMatrix4` (4×4) |
| TRS 分解 | 位置+旋转+缩放的直觉表示 | `_pos`, `_quat`, `_scale` |
| 四元数 | 无万向锁的旋转表示，支持 SLERP | `LQuaternion` |
| 双重表示 | 组件式和矩阵式互相转换 | `_flags` 标志位 + 懒惰计算 |
| 全局缓存 | 相同变换只存一份 | `_states` 哈希表 |
| 快速复合 | 均匀缩放时用四元数复合代替矩阵乘法 | `do_compose()` 快速路径 |
| 坐标系 | Z-up, Y-forward，GSG 层自动转换 | `cs_transform` |

**核心设计哲学**：
1. **不可变性**：`TransformState` 创建后不可修改，修改返回新实例
2. **懒惰计算**：矩阵和组件按需互相转换，避免不必要的计算
3. **全局唯一**：相同变换全局只有一份，节省内存和比较代价
4. **快速路径**：均匀缩放的常见情况走组件式复合，避免矩阵分解