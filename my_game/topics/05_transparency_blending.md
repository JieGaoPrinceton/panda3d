# 专题05：透明度与混合排序

## 目录
1. [问题背景](#1-问题背景)
2. [数学原理](#2-数学原理)
   - 2.1 Alpha 混合方程
   - 2.2 Porter-Duff 合成算子
   - 2.3 排序问题的数学本质
   - 2.4 OIT（顺序无关透明）算法
3. [工程实践](#3-工程实践)
   - 3.1 透明度模式选择
   - 3.2 深度写入与深度测试
   - 3.3 M_dual 双通道渲染
   - 3.4 粒子系统的透明处理
4. [Panda3D 源码解析](#4-panda3d-源码解析)
   - 4.1 TransparencyAttrib 模式
   - 4.2 CullResult::add_object() 透明处理
   - 4.3 ColorBlendAttrib 混合方程
5. [代码演示](#5-代码演示)
6. [性能分析](#6-性能分析)

---

## 1. 问题背景

透明度渲染是 3D 图形中最棘手的问题之一：

**核心矛盾**：Alpha 混合是**顺序相关**的——先画 A 再画 B，与先画 B 再画 A，结果不同。

```
正确顺序（从后到前）：
  背景 → 远处透明物体 → 近处透明物体

错误顺序（从前到后）：
  近处透明物体 → 远处透明物体 → 背景
  → 远处物体会错误地覆盖近处物体
```

**深度缓冲的局限**：深度缓冲只能处理不透明物体（写入最近深度），对透明物体无效——透明物体需要"透过"，但深度缓冲会阻止后面的物体被绘制。

---

## 2. 数学原理

### 2.1 Alpha 混合方程

GPU 的 Alpha 混合方程（OpenGL `glBlendFunc`）：

$$C_{out} = C_{src} \cdot F_{src} + C_{dst} \cdot F_{dst}$$

其中：
- $C_{src}$：片段着色器输出的颜色（源颜色）
- $C_{dst}$：帧缓冲中已有的颜色（目标颜色）
- $F_{src}$：源混合因子
- $F_{dst}$：目标混合因子

**标准 Alpha 混合**（`GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA`）：

$$C_{out} = C_{src} \cdot \alpha_{src} + C_{dst} \cdot (1 - \alpha_{src})$$

**加法混合**（粒子、光晕效果）（`GL_SRC_ALPHA, GL_ONE`）：

$$C_{out} = C_{src} \cdot \alpha_{src} + C_{dst}$$

**预乘 Alpha 混合**（`GL_ONE, GL_ONE_MINUS_SRC_ALPHA`）：

$$C_{out} = C_{src} + C_{dst} \cdot (1 - \alpha_{src})$$

其中 $C_{src}$ 已经预乘了 Alpha：$C_{src} = C_{original} \cdot \alpha$

### 2.2 Porter-Duff 合成算子

Porter-Duff（1984）定义了 12 种图像合成算子，最常用的是 **Over**：

$$C_{over} = C_A + C_B \cdot (1 - \alpha_A)$$
$$\alpha_{over} = \alpha_A + \alpha_B \cdot (1 - \alpha_A)$$

**Over 算子的性质**：
- **不满足交换律**：$A \text{ over } B \neq B \text{ over } A$
- **满足结合律**：$(A \text{ over } B) \text{ over } C = A \text{ over } (B \text{ over } C)$

这就是为什么透明物体必须从后到前排序——Over 算子要求先处理背景（$B$），再处理前景（$A$）。

### 2.3 排序问题的数学本质

**正确的 N 层透明合成**（从后到前）：

$$C_{final} = C_1 \cdot \alpha_1 + C_2 \cdot \alpha_2 \cdot (1-\alpha_1) + C_3 \cdot \alpha_3 \cdot (1-\alpha_1)(1-\alpha_2) + \ldots$$

**排序的困难**：
1. **循环遮挡**：三个三角形 A、B、C 可能形成 A 遮挡 B、B 遮挡 C、C 遮挡 A 的循环
2. **相交几何体**：两个透明物体相交时，无法用单一排序解决
3. **动态场景**：每帧都需要重新排序，代价 $O(N \log N)$

**Painter's Algorithm**（画家算法）：从后到前绘制，后绘制的覆盖先绘制的。
- 优点：简单，与 Alpha 混合天然兼容
- 缺点：无法处理循环遮挡和相交几何体

### 2.4 OIT（顺序无关透明）算法

**Depth Peeling**（深度剥离）：
- 第 1 遍：渲染最近的透明层
- 第 2 遍：渲染第 2 近的透明层（深度 > 第 1 遍的深度）
- 第 N 遍：渲染第 N 近的透明层
- 最后：从后到前合成所有层

代价：$O(N)$ 次渲染遍，$N$ 为透明层数。

**Weighted Blended OIT**（McGuire & Bavoil, 2013）：
- 不排序，直接累积加权颜色和权重
- 权重函数：$w(z, \alpha) = \alpha \cdot \max(0.01, \min(3000, \frac{0.03}{0.00001 + (z/200)^4}))$
- 最终颜色：$C_{final} = \frac{\sum C_i \cdot w_i}{\sum w_i}$
- 优点：单遍渲染，$O(1)$ 代价
- 缺点：近似结果，不完全正确

---

## 3. 工程实践

### 3.1 透明度模式选择

| 模式 | 适用场景 | 优点 | 缺点 |
|------|---------|------|------|
| `M_none` | 不透明物体 | 最快 | 无透明效果 |
| `M_alpha` | 一般透明（玻璃、水） | 正确混合 | 需要排序 |
| `M_binary` | 植被、栅栏（硬边缘） | 无需排序，可写深度 | 边缘锯齿 |
| `M_multisample` | 植被（MSAA 软化边缘） | 边缘平滑 | 需要 MSAA |
| `M_dual` | 复杂透明物体 | 减少排序问题 | 两次绘制 |
| `M_premultiplied_alpha` | 预乘 Alpha 纹理 | 更好的混合质量 | 纹理需预处理 |

### 3.2 深度写入与深度测试

透明物体的深度处理策略：

```
不透明物体：
  深度测试：开启（只绘制最近的）
  深度写入：开启（记录深度）

透明物体（M_alpha）：
  深度测试：开启（透明物体仍然被不透明物体遮挡）
  深度写入：关闭（不阻止后面的透明物体被绘制）

二值透明（M_binary）：
  深度测试：开启
  深度写入：开启（Alpha >= 0.5 的部分视为不透明）
```

**渲染顺序**：
1. 先渲染所有不透明物体（写入深度缓冲）
2. 再渲染透明物体（从后到前，不写深度）

### 3.3 M_dual 双通道渲染

`M_dual` 是 Panda3D 的特殊模式，将一个物体分成两部分渲染：

```
第一通道（不透明部分）：
  Alpha 测试：>= dual_opaque_level（默认 0.999）
  深度写入：开启
  混合：关闭
  → 渲染完全不透明的部分

第二通道（透明部分）：
  Alpha 测试：> 0（过滤完全透明的像素）
  深度写入：关闭
  混合：开启（标准 Alpha 混合）
  → 渲染半透明部分（放入 back_to_front bin）
```

**优势**：对于大部分不透明、小部分半透明的物体（如带透明边缘的树叶），可以正确处理不透明部分的深度，减少排序错误。

### 3.4 粒子系统的透明处理

粒子系统通常使用**加法混合**（Additive Blending）：

```
加法混合：C_out = C_src * alpha + C_dst
效果：粒子颜色叠加，越多粒子越亮
适用：火焰、爆炸、光晕、魔法效果
优点：无需排序（加法满足交换律）
```

**加法混合的数学性质**：

$$C_{out} = C_1 \cdot \alpha_1 + C_2 \cdot \alpha_2 + C_{bg}$$

由于加法满足交换律，粒子绘制顺序不影响最终结果！

---

## 4. Panda3D 源码解析

### 4.1 TransparencyAttrib 模式

**文件**：[`panda/src/pgraph/transparencyAttrib.h`](../../panda/src/pgraph/transparencyAttrib.h)

```cpp
// transparencyAttrib.h:33
class EXPCL_PANDA_PGRAPH TransparencyAttrib final : public RenderAttrib {
PUBLISHED:
  enum Mode {
    M_none = 0,           // 无透明，最快
    M_alpha = 1,          // 标准 Alpha 混合，Panda3D 自动排序（back_to_front bin）
    M_premultiplied_alpha, // 预乘 Alpha 混合（纹理已预乘）
    M_multisample,        // MSAA 多重采样透明（需要 MSAA 缓冲区）
    M_multisample_mask,   // MSAA 透明，不修改 Alpha 值
    M_binary,             // 二值透明：Alpha >= 0.5 不透明，< 0.5 完全透明
    M_dual,               // 双通道：不透明部分 + 透明部分分开渲染
  };
};
```

### 4.2 CullResult::add_object() 透明处理

**文件**：[`panda/src/pgraph/cullResult.cxx:107`](../../panda/src/pgraph/cullResult.cxx)

```cpp
void CullResult::
add_object(CullableObject &&object, const CullTraverser *traverser) {
  // ...

  // 检查透明度设置
  const TransparencyAttrib *trans;
  if (object._state->get_attrib(trans)) {
    switch (trans->get_mode()) {

    case TransparencyAttrib::M_alpha:
    case TransparencyAttrib::M_premultiplied_alpha:
      // M_alpha：添加 Alpha 测试（过滤 alpha=0 的像素，节省填充率）
      // 同时，对象会被放入 back_to_front bin（自动排序）
      object._state = object._state->compose(get_alpha_state());
      break;

    case TransparencyAttrib::M_binary:
      // M_binary：设置 Alpha 测试为 >= 0.5
      // 不需要排序，可以写深度缓冲
      object._state = object._state->compose(get_binary_state());
      break;

    case TransparencyAttrib::M_dual:
      if (!m_dual) {
        // 配置关闭时，退化为 M_alpha
        break;
      }
      {
        const CullBinAttrib *bin_attrib;
        if (!object._state->get_attrib(bin_attrib) ||
            bin_attrib->get_bin_name().empty()) {

          // ── 透明部分：复制对象，放入 back_to_front bin ──────────────
          CullableObject transparent_part(object);
          CPT(RenderState) transparent_state = get_dual_transparent_state();
          // transparent_state 包含：
          //   - AlphaTestAttrib: > 0（过滤完全透明像素）
          //   - TransparencyAttrib: M_alpha（开启混合）
          //   - DepthWriteAttrib: M_off（不写深度）
          transparent_part._state =
            object._state->compose(transparent_state);

          // 放入 back_to_front bin（会按深度排序）
          int transparent_bin_index =
            transparent_part._state->get_bin_index();
          CullBin *bin = get_bin(transparent_bin_index);
          bin->add_object(alloc_object(std::move(transparent_part)),
                          current_thread);

          // ── 不透明部分：原对象，放入默认 bin ──────────────────────
          // dual_opaque_state 包含：
          //   - AlphaTestAttrib: >= dual_opaque_level（默认 0.999）
          //   - TransparencyAttrib: M_none（关闭混合）
          //   - DepthWriteAttrib: M_on（写深度）
          object._state = object._state->compose(get_dual_opaque_state());
        }
        // 如果已有显式 bin，M_dual 退化为 M_alpha
      }
      break;
    }
  }

  // 根据 RenderState 中的 CullBinAttrib 决定放入哪个 bin
  int bin_index = object._state->get_bin_index();
  CullBin *bin = get_bin(bin_index);
  bin->add_object(alloc_object(std::move(object)), current_thread);
}
```

**关键辅助函数**：

```cpp
// cullResult.cxx:427
// get_alpha_state()：为 M_alpha 添加 Alpha 测试（过滤 alpha=0 像素）
CPT(RenderState) CullResult::get_alpha_state() {
  static CPT(RenderState) state = nullptr;
  if (state == nullptr) {
    state = RenderState::make(
      AlphaTestAttrib::make(AlphaTestAttrib::M_greater, 0.0f),
      // 注意：不关闭深度写入！这由 back_to_front bin 的排序保证正确性
      RenderState::get_max_priority()
    );
  }
  return state;
}

// get_binary_state()：M_binary 的 Alpha 测试
CPT(RenderState) CullResult::get_binary_state() {
  static CPT(RenderState) state = nullptr;
  if (state == nullptr) {
    state = RenderState::make(
      AlphaTestAttrib::make(AlphaTestAttrib::M_greater_equal, 0.5f),
      TransparencyAttrib::make(TransparencyAttrib::M_none),  // 关闭混合
      RenderState::get_max_priority()
    );
  }
  return state;
}

// get_dual_transparent_state()：M_dual 的透明部分
CPT(RenderState) CullResult::get_dual_transparent_state() {
  static CPT(RenderState) state = nullptr;
  if (state == nullptr) {
    state = RenderState::make(
      AlphaTestAttrib::make(AlphaTestAttrib::M_greater, 0.0f),
      TransparencyAttrib::make(TransparencyAttrib::M_alpha),
      DepthWriteAttrib::make(DepthWriteAttrib::M_off),
      RenderState::get_max_priority()
    );
  }
  return state;
}
```

### 4.3 ColorBlendAttrib 混合方程

**文件**：[`panda/src/pgraph/colorBlendAttrib.h`](../../panda/src/pgraph/colorBlendAttrib.h)

```cpp
// colorBlendAttrib.h:27
class EXPCL_PANDA_PGRAPH ColorBlendAttrib final : public RenderAttrib {
PUBLISHED:
  enum Mode {
    M_none,         // 禁用混合
    M_add,          // C_src * A + C_dst * B（标准混合）
    M_subtract,     // C_src * A - C_dst * B
    M_inv_subtract, // C_dst * B - C_src * A
    M_min,          // min(C_src, C_dst)
    M_max,          // max(C_src, C_dst)
  };

  enum Operand {
    O_zero,                      // 0
    O_one,                       // 1
    O_incoming_color,            // 源颜色 RGB
    O_one_minus_incoming_color,  // 1 - 源颜色 RGB
    O_fbuffer_color,             // 目标颜色 RGB
    O_one_minus_fbuffer_color,   // 1 - 目标颜色 RGB
    O_incoming_alpha,            // 源 Alpha
    O_one_minus_incoming_alpha,  // 1 - 源 Alpha（最常用）
    O_fbuffer_alpha,             // 目标 Alpha
    O_one_minus_fbuffer_alpha,   // 1 - 目标 Alpha
    O_constant_color,            // 常数颜色
    // ...
  };

  // 创建标准 Alpha 混合：C_out = C_src * alpha + C_dst * (1-alpha)
  static CPT(RenderAttrib) make(
    Mode mode,
    Operand a,      // 源因子
    Operand b,      // 目标因子
    Mode alpha_mode = M_none,
    Operand alpha_a = O_zero,
    Operand alpha_b = O_zero,
    const LColor &color = LColor::zero()
  );
};
```

---

## 5. 代码演示

### 5.1 Python：基本透明度设置

```python
from panda3d.core import TransparencyAttrib, NodePath

# ── 标准 Alpha 透明 ──────────────────────────────────────────────────────────
node = loader.load_model("glass.egg")
node.reparent_to(render)

# 方式 1：使用 NodePath 接口（推荐）
node.set_transparency(TransparencyAttrib.M_alpha)

# 方式 2：直接设置 Alpha 值（需要同时启用透明模式）
node.set_alpha_scale(0.5)  # 50% 透明
node.set_transparency(TransparencyAttrib.M_alpha)

# 方式 3：通过颜色设置 Alpha
node.set_color(1, 1, 1, 0.5)  # RGBA，A=0.5
node.set_transparency(TransparencyAttrib.M_alpha)

# ── 二值透明（植被）────────────────────────────────────────────────────────
tree = loader.load_model("tree.egg")
tree.reparent_to(render)
# M_binary：Alpha >= 0.5 不透明，< 0.5 完全透明
# 无需排序，性能好，适合植被
tree.set_transparency(TransparencyAttrib.M_binary)

# ── 双通道透明（复杂物体）──────────────────────────────────────────────────
complex_obj = loader.load_model("complex_glass.egg")
complex_obj.reparent_to(render)
# M_dual：不透明部分正确写深度，透明部分排序混合
complex_obj.set_transparency(TransparencyAttrib.M_dual)

# ── 关闭透明 ─────────────────────────────────────────────────────────────────
node.set_transparency(TransparencyAttrib.M_none)
# 或者
node.clear_transparency()
```

### 5.2 Python：自定义混合模式

```python
from panda3d.core import ColorBlendAttrib, RenderState

# ── 加法混合（粒子、光晕）──────────────────────────────────────────────────
particle_np = NodePath("particles")
particle_np.reparent_to(render)

# C_out = C_src * alpha + C_dst * 1（加法）
additive_blend = ColorBlendAttrib.make(
    ColorBlendAttrib.M_add,
    ColorBlendAttrib.O_incoming_alpha,      # 源因子：源 Alpha
    ColorBlendAttrib.O_one                  # 目标因子：1
)
particle_np.set_attrib(additive_blend)
# 加法混合不需要排序！

# ── 预乘 Alpha 混合 ──────────────────────────────────────────────────────────
# 适用于预乘 Alpha 的纹理（如 Photoshop 导出的 PNG）
premult_np = NodePath("premult")
premult_np.set_transparency(TransparencyAttrib.M_premultiplied_alpha)
# 等价于：C_out = C_src * 1 + C_dst * (1 - alpha)

# ── 减法混合（特殊效果）─────────────────────────────────────────────────────
# C_out = C_dst - C_src * alpha（使场景变暗）
subtract_blend = ColorBlendAttrib.make(
    ColorBlendAttrib.M_subtract,
    ColorBlendAttrib.O_incoming_alpha,
    ColorBlendAttrib.O_one
)
dark_effect_np = NodePath("dark_effect")
dark_effect_np.set_attrib(subtract_blend)

# ── 最大值混合（HDR 效果）──────────────────────────────────────────────────
max_blend = ColorBlendAttrib.make(
    ColorBlendAttrib.M_max,
    ColorBlendAttrib.O_one,
    ColorBlendAttrib.O_one
)
```

### 5.3 Python：手动控制渲染顺序

```python
from panda3d.core import CullBinAttrib

# ── 使用 Bin 控制渲染顺序 ────────────────────────────────────────────────────
# Panda3D 内置 Bin：
# "background"  sort=-100  不透明，最先渲染（天空盒）
# "opaque"      sort=10    不透明，默认
# "transparent" sort=20    透明，back_to_front 排序
# "fixed"       sort=40    固定顺序（HUD）

# 将节点放入特定 bin
sky_box.set_bin("background", 0)
sky_box.set_depth_write(False)  # 天空盒不写深度

# 透明物体自动放入 transparent bin（M_alpha 时）
glass.set_transparency(TransparencyAttrib.M_alpha)
# 等价于：glass.set_bin("transparent", 0)

# HUD 元素放入 fixed bin（不受深度影响）
hud.set_bin("fixed", 100)
hud.set_depth_test(False)
hud.set_depth_write(False)

# ── 自定义 Bin ───────────────────────────────────────────────────────────────
from panda3d.core import CullBinManager

bin_mgr = CullBinManager.get_global_ptr()

# 创建自定义 back_to_front bin（用于特殊透明效果）
bin_mgr.add_bin("my_transparent", CullBinManager.BT_back_to_front, 25)

# 将节点放入自定义 bin
special_glass.set_bin("my_transparent", 0)
special_glass.set_transparency(TransparencyAttrib.M_alpha)
```

### 5.4 Python：粒子系统透明

```python
from panda3d.core import (
    ColorBlendAttrib, TransparencyAttrib,
    DepthWriteAttrib, DepthTestAttrib
)

# ── 粒子系统最佳实践 ─────────────────────────────────────────────────────────
class ParticleSystem:
    def __init__(self, parent):
        self.root = parent.attach_new_node("particles")

        # 加法混合：无需排序，适合发光粒子
        self.root.set_attrib(ColorBlendAttrib.make(
            ColorBlendAttrib.M_add,
            ColorBlendAttrib.O_incoming_alpha,
            ColorBlendAttrib.O_one
        ))

        # 不写深度（粒子不阻挡其他物体）
        self.root.set_depth_write(False)

        # 仍然进行深度测试（粒子被不透明物体遮挡）
        self.root.set_depth_test(True)

        # 放入 transparent bin（在不透明物体之后渲染）
        self.root.set_bin("transparent", 0)

        # 关闭背面剔除（粒子是双面的）
        self.root.set_two_sided(True)

# ── 烟雾粒子（需要排序）─────────────────────────────────────────────────────
class SmokeParticles:
    def __init__(self, parent):
        self.root = parent.attach_new_node("smoke")

        # 标准 Alpha 混合（烟雾需要正确的混合顺序）
        self.root.set_transparency(TransparencyAttrib.M_alpha)
        self.root.set_depth_write(False)

        # 注意：M_alpha 会自动放入 back_to_front bin
        # 但粒子之间的排序仍然可能不正确（粒子相互穿插）
```

### 5.5 GLSL：Shader 中的透明度处理

```glsl
// 片段着色器中的透明度处理

// 方式 1：直接输出 Alpha（配合 M_alpha 使用）
void main() {
    vec4 color = texture(p3d_Texture0, v_texcoord);
    // 直接输出，GPU 混合单元处理混合
    frag_color = color;
}

// 方式 2：Alpha 测试（配合 M_binary 使用，或手动丢弃）
void main() {
    vec4 color = texture(p3d_Texture0, v_texcoord);
    // 手动 Alpha 测试（比 M_binary 更灵活）
    if (color.a < 0.1) discard;  // 完全透明的像素直接丢弃
    frag_color = color;
}

// 方式 3：预乘 Alpha（配合 M_premultiplied_alpha 使用）
void main() {
    vec4 color = texture(p3d_Texture0, v_texcoord);
    // 输出预乘 Alpha 颜色
    frag_color = vec4(color.rgb * color.a, color.a);
}

// 方式 4：OIT Weighted Blended（顺序无关透明）
layout(location = 0) out vec4 accum;   // 累积颜色
layout(location = 1) out float reveal; // 透明度累积

void main() {
    vec4 color = texture(p3d_Texture0, v_texcoord);
    float alpha = color.a;

    // 权重函数（根据深度和 Alpha 计算）
    float weight = alpha * max(0.01,
        min(3000.0, 0.03 / (1e-5 + pow(gl_FragCoord.z / 200.0, 4.0))));

    accum = vec4(color.rgb * alpha, alpha) * weight;
    reveal = alpha;
}
```

---

## 6. 性能分析

### 6.1 各透明模式性能对比

| 模式 | 排序代价 | 渲染代价 | 正确性 | 适用场景 |
|------|---------|---------|--------|---------|
| M_none | 无 | 最低 | N/A | 不透明物体 |
| M_binary | 无 | 低 | 硬边缘 | 植被、栅栏 |
| M_multisample | 无 | 中（需 MSAA） | 软边缘 | 植被（高质量） |
| M_alpha | O(N log N) | 中 | 正确（无循环遮挡） | 玻璃、水面 |
| M_dual | O(N log N) | 高（2次绘制） | 更好 | 复杂透明物体 |
| 加法混合 | 无 | 低 | 近似 | 粒子、光晕 |

### 6.2 排序代价分析

```python
# 测量透明排序代价
import time

# 场景：1000 个透明物体
transparent_nodes = []
for i in range(1000):
    node = loader.load_model("glass_shard.egg")
    node.reparent_to(render)
    node.set_transparency(TransparencyAttrib.M_alpha)
    transparent_nodes.append(node)

# 每帧排序代价：O(N log N) = 1000 * log(1000) ≈ 10000 次比较
# 典型代价：~0.5ms（CPU 端）

# 优化：减少透明物体数量
# 将多个小透明物体合并为一个大网格
```

### 6.3 常见性能陷阱

```python
# ❌ 错误：不透明物体启用透明模式
opaque_rock = loader.load_model("rock.egg")
opaque_rock.set_transparency(TransparencyAttrib.M_alpha)  # 不必要！
# 问题：rock 会被放入 back_to_front bin，每帧排序，且渲染顺序错误

# ✅ 正确：只对真正透明的物体启用透明模式
glass = loader.load_model("glass.egg")
glass.set_transparency(TransparencyAttrib.M_alpha)

# ❌ 错误：透明物体写深度缓冲
glass.set_depth_write(True)   # 默认 M_alpha 已关闭深度写入
# 问题：透明物体写入深度后，后面的物体无法被看到

# ✅ 正确：M_alpha 自动关闭深度写入（通过 back_to_front bin 的排序保证）

# ❌ 错误：大量粒子使用 M_alpha（需要排序）
for i in range(10000):
    particle = create_particle()
    particle.set_transparency(TransparencyAttrib.M_alpha)  # 10000 个粒子排序！

# ✅ 正确：粒子使用加法混合（无需排序）
for i in range(10000):
    particle = create_particle()
    particle.set_attrib(ColorBlendAttrib.make(
        ColorBlendAttrib.M_add,
        ColorBlendAttrib.O_incoming_alpha,
        ColorBlendAttrib.O_one
    ))
    particle.set_depth_write(False)

# ❌ 错误：透明物体不设置 bin，与不透明物体混在一起
glass.set_transparency(TransparencyAttrib.M_alpha)
# 注意：M_alpha 会自动放入 transparent bin，这是正确的
# 但如果手动设置了错误的 bin：
glass.set_bin("opaque", 0)  # 错误！透明物体放入不透明 bin
glass.set_transparency(TransparencyAttrib.M_alpha)
# 问题：不会按深度排序，透明效果错误
```

### 6.4 透明度与阴影的交互

```python
# 透明物体的阴影处理是个难题：
# 1. 透明物体投射阴影：Shadow Map 无法处理半透明（只有深度信息）
# 2. 解决方案：使用 Alpha 测试（M_binary）投射阴影

# 让透明物体投射正确的阴影（使用 Alpha 测试）
glass_with_shadow = loader.load_model("stained_glass.egg")
glass_with_shadow.set_transparency(TransparencyAttrib.M_alpha)  # 渲染时半透明

# 阴影渲染时使用 Alpha 测试（只有不透明部分投射阴影）
# 通过 Tag State 为阴影相机设置不同的渲染状态
shadow_state = RenderState.make(
    TransparencyAttrib.make(TransparencyAttrib.M_binary)
)
base.cam.node().set_tag_state_key("shadow_pass")
glass_with_shadow.set_tag("shadow_pass", "alpha_test")
base.cam.node().set_tag_state("alpha_test", shadow_state)
```

---

## 小结

| 概念 | 核心思想 | Panda3D 实现 |
|------|----------|-------------|
| Alpha 混合 | 源颜色与目标颜色加权混合 | `ColorBlendAttrib` |
| 排序问题 | Over 算子不满足交换律 | `back_to_front` bin |
| M_binary | Alpha 阈值二值化，无需排序 | `AlphaTestAttrib >= 0.5` |
| M_dual | 不透明+透明两次绘制 | 复制对象到两个 bin |
| 加法混合 | 满足交换律，无需排序 | `ColorBlendAttrib.M_add` |
| 深度写入 | 透明物体不写深度 | `DepthWriteAttrib.M_off` |

**核心设计哲学**：
1. **自动排序**：`M_alpha` 自动将对象放入 `back_to_front` bin，无需手动排序
2. **模式选择**：根据透明类型选择最合适的模式（性能 vs 正确性权衡）
3. **加法混合例外**：粒子等效果使用加法混合，完全绕过排序问题
4. **M_dual 折中**：对复杂物体，将不透明和透明部分分开处理，减少排序错误