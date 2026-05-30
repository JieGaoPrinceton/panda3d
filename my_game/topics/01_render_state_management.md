# 专题01：渲染管线与状态管理

> 对应源码：`panda/src/display/`、`panda/src/pgraph/`、`panda/src/glstuff/`

---

## 目录

1. [问题背景](#1-问题背景)
2. [数学原理](#2-数学原理)
3. [工程实践](#3-工程实践)
4. [Panda3D 源码解析](#4-panda3d-源码解析)
5. [代码演示](#5-代码演示)
6. [性能分析与调优](#6-性能分析与调优)

---

## 1. 问题背景

### 1.1 什么是渲染状态

GPU 是一个**有状态的状态机**。在发出绘制命令（`glDrawElements`）之前，必须先配置好所有渲染参数：

```
当前绑定的 Shader Program
当前绑定的纹理（Texture Unit 0~N）
深度测试函数（GL_LESS / GL_LEQUAL / ...）
深度写入开关（glDepthMask）
面剔除模式（GL_BACK / GL_FRONT / GL_NONE）
混合函数（glBlendFunc）
模板测试参数
裁剪矩形（glScissor）
视口（glViewport）
...（共数十个状态）
```

每次状态切换都有 **CPU→GPU 同步开销**，在极端情况下（如每个 Draw Call 都切换 Shader）会导致 GPU 流水线停顿（Pipeline Stall）。

### 1.2 核心矛盾

- **正确性**：每个物体必须用正确的状态渲染
- **性能**：状态切换越少越好
- **灵活性**：场景图中任意节点可以设置任意状态

这三者之间存在根本性张力，是渲染引擎设计的核心难题之一。

---

## 2. 数学原理

### 2.1 状态的代数结构

渲染状态可以被建模为一个**幺半群（Monoid）**：

```
设 S 为所有可能的渲染状态集合
操作 ∘ : S × S → S  （状态组合/继承）
单位元 e ∈ S         （空状态，不改变任何设置）

满足：
  结合律：(a ∘ b) ∘ c = a ∘ (b ∘ c)
  单位元：e ∘ a = a ∘ e = a
```

**场景图中的状态传播**就是沿树路径的幺半群乘法：

```
root_state ∘ node1_state ∘ node2_state ∘ ... ∘ leaf_state = 最终渲染状态
```

### 2.2 状态组合规则（优先级语义）

每个 `RenderAttrib` 有一个**优先级（priority）**，组合时高优先级覆盖低优先级：

```
compose(parent_attrib, child_attrib):
  if child_attrib.priority >= parent_attrib.priority:
    return child_attrib   // 子节点覆盖父节点
  else:
    return parent_attrib  // 父节点保持
```

这实现了 CSS 类似的**层叠（Cascade）**语义。

### 2.3 状态缓存的数学基础

`RenderState` 的全局缓存利用了**结构共享（Structural Sharing）**：

```
若 state_A == state_B（所有 attrib 相同）
则 state_A 和 state_B 是同一个对象（指针相同）

推论：
  state_A == state_B  ⟺  &state_A == &state_B
  状态比较 O(N) → 指针比较 O(1)
```

`compose()` 的结果也被缓存（二维哈希表）：

```
cache[state_A][state_B] = state_A ∘ state_B

命中率分析：
  场景图中相同路径的节点会产生相同的 compose 调用
  缓存命中率通常 > 90%
```

### 2.4 差量更新的信息论视角

设当前 GPU 状态为 `S_current`，目标状态为 `S_target`。

**朴素方法**：每帧全量设置所有状态，代价 O(N)（N = 状态数量）

**差量方法**：只设置 `S_target - S_current`（集合差），代价 O(|diff|)

用位图（BitMask）表示"哪些状态已同步"：

```
_state_mask: 每个 bit 对应一个 attrib slot
  bit = 1 → 该 attrib 已同步到 GPU
  bit = 0 → 该 attrib 需要重新设置

更新条件：
  需要更新 slot i ⟺ (target[i] ≠ current[i]) OR (mask[i] == 0)
```

---

## 3. 工程实践

### 3.1 状态排序（State Sorting）

**核心思想**：将渲染顺序从"场景图顺序"改为"状态相似度顺序"，最小化状态切换次数。

```
朴素顺序（场景图 DFS）：
  obj1(shader=A, tex=X) → obj2(shader=B, tex=Y) → obj3(shader=A, tex=Z)
  状态切换：A→B→A（2次 Shader 切换）

排序后：
  obj1(shader=A, tex=X) → obj3(shader=A, tex=Z) → obj2(shader=B, tex=Y)
  状态切换：A→B（1次 Shader 切换）
```

**排序键设计**（从重到轻）：

```
1. Shader Program（切换代价最高，~1ms）
2. 纹理绑定（~0.1ms）
3. 混合状态（~0.01ms）
4. 深度状态（~0.01ms）
5. 其他轻量状态
```

Panda3D 的 [`CullBinStateSorted`](panda/src/cull/cullBinStateSorted.cxx) 实现了按 `RenderState` 指针排序（等价于按状态内容排序，因为相同状态共享指针）。

### 3.2 状态分组（State Batching）

**Draw Call 合并**：将使用相同状态的多个物体合并为一个 Draw Call：

```
条件：
  - 相同 Shader
  - 相同纹理集合
  - 相同混合/深度状态
  - 顶点格式兼容

合并方式：
  - 静态合并：预处理阶段合并（SceneGraphReducer）
  - 动态合并：运行时合并（Instancing）
```

Panda3D 的 [`SceneGraphReducer`](panda/src/pgraph/sceneGraphReducer.h) 提供静态合并：

```python
reducer = SceneGraphReducer()
reducer.apply_attribs(scene)   # 将状态下推到叶节点
reducer.flatten(scene, SceneGraphReducer.FT_full)  # 合并几何体
```

### 3.3 状态失效（State Invalidation）

某些操作会导致 `_state_mask` 部分位被清零（强制重新设置）：

| 触发事件 | 失效的状态 |
|----------|-----------|
| Shader 切换 | 纹理 slot（需重新绑定到新 Shader 的 uniform） |
| FBO 切换 | 视口、裁剪矩形 |
| 上下文丢失（窗口最小化） | 全部状态 |
| 多线程上下文切换 | 全部状态 |

### 3.4 Uber Shader 策略

**问题**：频繁切换 Shader 代价极高。

**解法**：将多个功能合并到一个"超级 Shader"，用 `#define` 或 uniform 开关控制：

```glsl
// Uber Shader 示例
uniform int u_has_normal_map;
uniform int u_has_shadow;
uniform int u_num_lights;

void main() {
    vec3 normal = vertex_normal;
    
    #ifdef HAS_NORMAL_MAP
    if (u_has_normal_map > 0) {
        normal = texture(normal_map, uv).rgb * 2.0 - 1.0;
    }
    #endif
    
    // 光照计算
    for (int i = 0; i < u_num_lights; i++) {
        // ...
    }
}
```

**权衡**：
- 优点：减少 Shader 切换
- 缺点：单个 Shader 更复杂，可能影响 GPU 寄存器分配

---

## 4. Panda3D 源码解析

### 4.1 RenderState：不可变状态集合

**源码位置：** [`renderState.cxx`](panda/src/pgraph/renderState.cxx)

```cpp
class RenderState : public NodeCachedReferenceCount {
    // 每个 slot 存储一个 RenderAttrib
    Attribute _attributes[RenderAttribRegistry::_max_slots];
    
    // 哪些 slot 有值（位图）
    SlotMask _filled_slots;
    
    // compose() 结果缓存（二维哈希表）
    CompositionCache _composition_cache;
    
    // 全局状态池（所有存活的 RenderState 对象）
    static States _states;  // pset<const RenderState *>
    static LightReMutex *_states_lock;
};
```

**`compose()` 的缓存机制：**

```cpp
// renderState.cxx:339
CPT(RenderState) RenderState::compose(const RenderState *other) const {
    // 快速路径：空状态
    if (is_empty()) return other;
    if (other->is_empty()) return this;

    // 查缓存
    int index = _composition_cache.find(other);
    if (index != -1) {
        Composition &comp = _composition_cache.modify_data(index);
        if (comp._result != nullptr) {
            _cache_stats.inc_hits();
            return comp._result;  // 缓存命中！
        }
    }

    // 缓存未命中，计算新结果
    _cache_stats.inc_misses();
    CPT(RenderState) result = do_compose(other);

    // 双向记录缓存条目（便于析构时清理）
    _composition_cache[other]._result = result;
    other->_composition_cache[this]._result = nullptr;  // 反向只记录 key

    result->cache_ref();  // 防止被 GC
    return result;
}
```

**`do_compose()` 的实际合并逻辑：**

```cpp
CPT(RenderState) RenderState::do_compose(const RenderState *other) const {
    // 遍历两个状态的所有 slot
    SlotMask mask = _filled_slots | other->_filled_slots;
    
    RenderState *new_state = new RenderState;
    int slot = mask.get_lowest_on_bit();
    while (slot >= 0) {
        const RenderAttrib *a = _attributes[slot]._attrib;  // 父状态的 attrib
        const RenderAttrib *b = other->_attributes[slot]._attrib;  // 子状态的 attrib
        
        if (b == nullptr) {
            // 子状态没有这个 attrib，继承父状态
            new_state->_attributes[slot] = _attributes[slot];
        } else if (a == nullptr) {
            // 父状态没有这个 attrib，使用子状态
            new_state->_attributes[slot] = other->_attributes[slot];
        } else {
            // 两者都有，调用 attrib 自身的 compose 逻辑（考虑优先级）
            int result = a->compose(b);
            new_state->_attributes[slot]._attrib = result;
        }
        
        mask.clear_bit(slot);
        slot = mask.get_lowest_on_bit();
    }
    
    // 在全局池中查找或注册（保证唯一性）
    return return_new(new_state);
}
```

### 4.2 GSG 的差量状态更新

**源码位置：** [`glGraphicsStateGuardian_src.cxx:12760`](panda/src/glstuff/glGraphicsStateGuardian_src.cxx:12760)

```cpp
void CLP(GraphicsStateGuardian)::set_state_and_transform(
        const RenderState *target, const TransformState *transform) {

    // ── 变换矩阵 ──────────────────────────────────────────────
    if (transform != _internal_transform) {
        _internal_transform = transform;
        do_issue_transform();  // 上传 ModelView 矩阵到 Shader
    }

    // ── 快速路径：状态完全相同 ────────────────────────────────
    if (target == _state_rs && (_state_mask | _inv_state_mask).is_all_on()) {
        // 只需更新 Shader 的 transform uniform（已在上面处理）
        return;
    }

    _target_rs = target;

    // ── Shader 切换（代价最高，优先处理）────────────────────────
    determine_target_shader();
    if (_target_shader != _state_shader) {
        do_issue_shader();   // glUseProgram()
        _state_shader = _target_shader;
        // Shader 切换后纹理 slot 需要重新绑定
        _state_mask.clear_bit(TextureAttrib::get_class_slot());
    }

    // 更新 Shader Uniforms（矩阵、光照参数等）
    if (_current_shader_context) {
        _current_shader_context->set_state_and_transform(
            target, transform,
            _scene_setup->get_camera_transform(),
            _projection_mat);
    }

    // ── 逐属性差量更新 ────────────────────────────────────────
    // 模式：只有当 attrib 指针变化 OR 该 slot 未同步时才调用 do_issue_*()

    // 深度测试
    int depth_test_slot = DepthTestAttrib::get_class_slot();
    if (_target_rs->get_attrib(depth_test_slot) != _state_rs->get_attrib(depth_test_slot)
        || !_state_mask.get_bit(depth_test_slot)) {
        do_issue_depth_test();   // glDepthFunc() + glEnable/Disable(GL_DEPTH_TEST)
        _state_mask.set_bit(depth_test_slot);
    }

    // 深度写入
    int depth_write_slot = DepthWriteAttrib::get_class_slot();
    if (_target_rs->get_attrib(depth_write_slot) != _state_rs->get_attrib(depth_write_slot)
        || !_state_mask.get_bit(depth_write_slot)) {
        do_issue_depth_write();  // glDepthMask()
        _state_mask.set_bit(depth_write_slot);
    }

    // 面剔除
    int cull_face_slot = CullFaceAttrib::get_class_slot();
    if (_target_rs->get_attrib(cull_face_slot) != _state_rs->get_attrib(cull_face_slot)
        || !_state_mask.get_bit(cull_face_slot)) {
        do_issue_cull_face();    // glCullFace() + glEnable/Disable(GL_CULL_FACE)
        _state_mask.set_bit(cull_face_slot);
    }

    // 纹理（代价较高，需要绑定多个纹理单元）
    int texture_slot = TextureAttrib::get_class_slot();
    if (_target_rs->get_attrib(texture_slot) != _state_rs->get_attrib(texture_slot)
        || !_state_mask.get_bit(texture_slot)) {
        do_issue_texture();      // glActiveTexture() + glBindTexture() × N
        _state_mask.set_bit(texture_slot);
    }

    // 混合
    int transparency_slot = TransparencyAttrib::get_class_slot();
    if (_target_rs->get_attrib(transparency_slot) != _state_rs->get_attrib(transparency_slot)
        || !_state_mask.get_bit(transparency_slot)) {
        do_issue_blending();     // glBlendFunc() + glEnable/Disable(GL_BLEND)
        _state_mask.set_bit(transparency_slot);
    }

    // ... 其他属性（光照、雾、模板、裁剪等）

    _state_rs = target;  // 记录当前已同步状态
}
```

### 4.3 RenderAttrib 的优先级系统

**源码位置：** [`renderAttrib.h`](panda/src/pgraph/renderAttrib.h)

```cpp
class RenderAttrib {
public:
    // 每个 attrib 有一个优先级（默认 0）
    // 高优先级的 attrib 在 compose 时覆盖低优先级
    virtual int get_override() const { return _override; }

    // 子类实现具体的 compose 逻辑
    virtual CPT(RenderAttrib) compose(const RenderAttrib *other) const;
};

// 以 DepthTestAttrib 为例
CPT(RenderAttrib) DepthTestAttrib::compose(const RenderAttrib *other) const {
    const DepthTestAttrib *ta = (const DepthTestAttrib *)other;
    // 高优先级覆盖低优先级
    if (ta->get_override() >= get_override()) {
        return other;  // 子节点（other）优先级更高，使用子节点的值
    }
    return this;       // 父节点优先级更高，保持父节点的值
}
```

---

## 5. 代码演示

### 5.1 Python：基本状态设置

```python
from panda3d.core import (
    NodePath, GeomNode, RenderState,
    DepthTestAttrib, DepthWriteAttrib, CullFaceAttrib,
    TransparencyAttrib, ColorBlendAttrib,
    LVecBase4f
)

# ── 场景图状态继承 ────────────────────────────────────────────
root = render  # 场景根节点

# 父节点设置深度测试
root.set_depth_test(True)
root.set_depth_write(True)

# 子节点覆盖：关闭深度写入（透明物体常用）
transparent_node = root.attach_new_node("transparent")
transparent_node.set_depth_write(False)
transparent_node.set_transparency(TransparencyAttrib.M_alpha)

# 孙节点继承父链的所有状态（深度测试=True，深度写入=False，透明=alpha）
leaf = transparent_node.attach_new_node("leaf")
# leaf 自动继承上面的状态，无需重复设置


# ── 手动构建 RenderState ──────────────────────────────────────
state = RenderState.make(
    DepthTestAttrib.make(DepthTestAttrib.M_less),
    DepthWriteAttrib.make(DepthWriteAttrib.M_off),
    CullFaceAttrib.make(CullFaceAttrib.M_cull_none),
    TransparencyAttrib.make(TransparencyAttrib.M_alpha),
)

# 应用到节点
node.set_state(state)


# ── 状态组合（compose）────────────────────────────────────────
parent_state = RenderState.make(
    DepthTestAttrib.make(DepthTestAttrib.M_less),
)
child_state = RenderState.make(
    DepthWriteAttrib.make(DepthWriteAttrib.M_off),
)

# compose：子状态叠加到父状态上
combined = parent_state.compose(child_state)
# combined 包含：depth_test=less, depth_write=off


# ── 优先级覆盖 ────────────────────────────────────────────────
# 父节点强制设置（高优先级），子节点无法覆盖
root.set_depth_test(True, 100)  # priority=100

child = root.attach_new_node("child")
child.set_depth_test(False, 50)  # priority=50，低于父节点，无效！
# child 实际使用 depth_test=True（父节点的高优先级设置）
```

### 5.2 Python：状态排序优化

```python
from panda3d.core import CullBinManager, CullBinAttrib

# ── 配置 Bin 排序 ─────────────────────────────────────────────
bin_mgr = CullBinManager.get_global_ptr()

# 查看默认 Bin
for i in range(bin_mgr.get_num_bins()):
    name = bin_mgr.get_bin_name(i)
    sort = bin_mgr.get_bin_sort(i)
    btype = bin_mgr.get_bin_type(i)
    print(f"Bin[{i}]: name={name}, sort={sort}, type={btype}")

# 输出示例：
# Bin[0]: name=background, sort=-100, type=BT_fixed
# Bin[1]: name=opaque,     sort=0,    type=BT_state_sorted  ← 按状态排序
# Bin[2]: name=transparent,sort=10,   type=BT_back_to_front ← 从后往前
# Bin[3]: name=fixed,      sort=20,   type=BT_fixed
# Bin[4]: name=unsorted,   sort=30,   type=BT_unsorted

# ── 将物体放入特定 Bin ────────────────────────────────────────
# 不透明物体（默认在 opaque bin，按状态排序）
opaque_obj.set_bin("opaque", 0)

# 透明物体（在 transparent bin，从后往前排序）
transparent_obj.set_bin("transparent", 0)

# GUI 元素（固定顺序，不受深度影响）
gui_element.set_bin("fixed", 10)  # sort=10 决定 GUI 内部顺序

# ── 自定义 Bin ────────────────────────────────────────────────
# 创建一个新的 state_sorted bin，用于特殊效果
bin_mgr.add_bin("effects", CullBinManager.BT_state_sorted, 5)
effect_obj.set_bin("effects", 0)
```

### 5.3 Python：监控状态切换次数

```python
from panda3d.core import PStatClient, RenderState, TransformState

# 连接 PStats 性能分析器
PStatClient.connect()

# 在游戏循环中监控
def monitor_state_changes(task):
    # 查看 RenderState 缓存统计
    num_states = RenderState.get_num_states()
    num_unused = RenderState.get_num_unused_states()
    print(f"RenderStates: {num_states} total, {num_unused} unused")

    # 查看 TransformState 缓存统计
    num_transforms = TransformState.get_num_states()
    print(f"TransformStates: {num_transforms} total")

    return task.cont

taskMgr.add(monitor_state_changes, "monitor", sort=50)

# 手动触发垃圾回收（清理未使用的缓存状态）
RenderState.clear_cache()
TransformState.clear_cache()
```

### 5.4 Python：强制状态刷新

```python
# 某些情况下需要强制 GSG 重新设置所有状态
# （例如：外部 OpenGL 代码修改了状态后）

from panda3d.core import GraphicsEngine

engine = base.graphicsEngine
for win in engine.windows:
    gsg = win.gsg
    if gsg:
        gsg.clear_state_and_transform()  # 清空 _state_mask，强制全量更新
```

### 5.5 GLSL：Shader 内的状态感知

```glsl
// vertex.glsl
#version 330 core

// Panda3D 自动注入的矩阵 uniform
uniform mat4 p3d_ModelViewProjectionMatrix;  // MVP
uniform mat4 p3d_ModelViewMatrix;            // MV
uniform mat3 p3d_NormalMatrix;               // 法线矩阵（MV的逆转置）

// 自定义 uniform（通过 set_shader_input 设置）
uniform vec4 u_color_tint;
uniform float u_time;

in vec4 p3d_Vertex;
in vec3 p3d_Normal;
in vec2 p3d_MultiTexCoord0;

out vec3 v_normal_ws;
out vec2 v_uv;

void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    v_normal_ws = normalize(p3d_NormalMatrix * p3d_Normal);
    v_uv = p3d_MultiTexCoord0;
}
```

```glsl
// fragment.glsl
#version 330 core

uniform sampler2D p3d_Texture0;
uniform vec4 u_color_tint;

in vec3 v_normal_ws;
in vec2 v_uv;

out vec4 frag_color;

void main() {
    vec4 tex_color = texture(p3d_Texture0, v_uv);
    frag_color = tex_color * u_color_tint;
}
```

```python
# Python 端设置 Shader
from panda3d.core import Shader, ShaderAttrib

shader = Shader.load(Shader.SL_GLSL,
    vertex="vertex.glsl",
    fragment="fragment.glsl")

node.set_shader(shader)
node.set_shader_input("u_color_tint", LVecBase4f(1, 0.5, 0.5, 1))
node.set_shader_input("u_time", 0.0)

# 每帧更新 time
def update_shader(task):
    node.set_shader_input("u_time", task.time)
    return task.cont
taskMgr.add(update_shader, "update_shader")
```

### 5.6 C++：自定义 RenderAttrib

```cpp
// 自定义一个 WireframeAttrib（示例）
class WireframeAttrib : public RenderAttrib {
PUBLISHED:
    static CPT(RenderAttrib) make(bool enabled) {
        WireframeAttrib *attrib = new WireframeAttrib(enabled);
        return return_new(attrib);
    }

    bool get_enabled() const { return _enabled; }

public:
    // compose：子节点的设置覆盖父节点
    virtual CPT(RenderAttrib) compose(const RenderAttrib *other) const override {
        const WireframeAttrib *ta = (const WireframeAttrib *)other;
        if (ta->get_override() >= get_override()) {
            return other;
        }
        return this;
    }

    // 注册到 GSG（在 do_issue_* 中调用 glPolygonMode）
    static int get_class_slot() { return _attrib_slot; }

private:
    WireframeAttrib(bool enabled) : _enabled(enabled) {}
    bool _enabled;
    static int _attrib_slot;
};
```

---

## 6. 性能分析与调优

### 6.1 Draw Call 数量 vs 状态切换次数

```
性能公式（近似）：
  帧时间 ≈ N_drawcall × T_drawcall + N_statechange × T_statechange + N_vertex × T_vertex

典型值（现代 GPU，CPU 端）：
  T_drawcall    ≈ 5~50 μs（CPU 提交开销）
  T_statechange ≈ 0.1~10 μs（取决于状态类型）
  T_vertex      ≈ 极小（GPU 并行处理）

优化目标：
  减少 N_drawcall（合并几何体、Instancing）
  减少 N_statechange（状态排序、Uber Shader）
```

### 6.2 各状态切换代价排行

| 状态 | 切换代价 | 优化策略 |
|------|----------|----------|
| Shader Program | ★★★★★ | Uber Shader、减少 Shader 种类 |
| Render Target（FBO） | ★★★★★ | 合并 Pass、Render Graph 自动调度 |
| 纹理绑定 | ★★★★☆ | Texture Array、Bindless Texture |
| Uniform Buffer | ★★★☆☆ | UBO 批量更新 |
| 深度/混合状态 | ★★☆☆☆ | Pipeline State Object（Vulkan/DX12） |
| 顶点格式 | ★★☆☆☆ | 统一顶点格式 |

### 6.3 RenderState 缓存命中率优化

```python
# 避免每帧创建新的 RenderState（会导致缓存污染）

# ❌ 错误：每帧创建新状态
def bad_update(task):
    state = RenderState.make(
        ColorAttrib.make_flat(LVecBase4f(task.time % 1, 0, 0, 1))  # 每帧不同！
    )
    node.set_state(state)
    return task.cont

# ✅ 正确：缓存状态对象，只在需要时更新
cached_states = {}
def good_update(task):
    # 离散化颜色值，减少唯一状态数量
    r = int(task.time * 10) % 10 / 10.0  # 只有 10 种值
    if r not in cached_states:
        cached_states[r] = RenderState.make(
            ColorAttrib.make_flat(LVecBase4f(r, 0, 0, 1))
        )
    node.set_state(cached_states[r])
    return task.cont
```

### 6.4 状态排序的实际效果

```
场景：1000 个物体，10 种 Shader，每种 Shader 100 个物体

未排序（场景图顺序）：
  平均每个物体切换 Shader 概率 ≈ 90%
  Shader 切换次数 ≈ 900 次

按 Shader 排序后：
  Shader 切换次数 = 9 次（10 种 Shader 之间的边界）
  性能提升：100x（Shader 切换）

实测（典型场景）：
  排序前：帧时间 16ms（60fps 边缘）
  排序后：帧时间 8ms（120fps）
```

---

## 小结

| 概念 | 核心思想 | Panda3D 实现 |
|------|----------|-------------|
| RenderState 不可变缓存 | 相同状态共享指针，O(1) 比较 | [`renderState.cxx`](panda/src/pgraph/renderState.cxx) 全局 `_states` 池 |
| compose() 缓存 | 状态组合结果缓存，避免重复计算 | `_composition_cache` 二维哈希表 |
| 差量更新 | `_state_mask` 位图，只更新变化的属性 | [`glGraphicsStateGuardian_src.cxx:12760`](panda/src/glstuff/glGraphicsStateGuardian_src.cxx:12760) |
| Bin 排序 | 按状态相似度重排绘制顺序 | [`CullBinStateSorted`](panda/src/cull/cullBinStateSorted.cxx) |
| 优先级继承 | 高优先级父节点状态不被子节点覆盖 | `RenderAttrib::get_override()` |