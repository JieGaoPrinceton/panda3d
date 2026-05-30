# Panda3D 着色器（Shader）工作原理深度解析

> 基于对 Panda3D 源码的深入研究，涵盖以下核心文件：
> - [`panda/src/gobj/shader.h`](../panda/src/gobj/shader.h) — 核心数据结构
> - [`panda/src/gobj/shader.cxx`](../panda/src/gobj/shader.cxx) — 参数解析逻辑
> - [`panda/src/glstuff/glShaderContext_src.h`](../panda/src/glstuff/glShaderContext_src.h) — GL 着色器上下文接口
> - [`panda/src/glstuff/glShaderContext_src.cxx`](../panda/src/glstuff/glShaderContext_src.cxx) — 编译/绑定/参数传递实现
> - [`panda/src/pgraph/shaderAttrib.h`](../panda/src/pgraph/shaderAttrib.h) — 渲染状态属性
> - [`panda/src/pgraphnodes/shaderGenerator.cxx`](../panda/src/pgraphnodes/shaderGenerator.cxx) — AutoShader 自动生成

---

## 一、整体架构分层

```
Python/C++ 用户代码
        │  set_shader() / set_shader_input()
        ▼
  ShaderAttrib          ← RenderState 的一部分（pgraph 层）
        │  compose_impl() 合并继承链
        ▼
    Shader 对象          ← 持有 GLSL/Cg 源码文本 + 参数规格表
        │  prepare_now()
        ▼
  ShaderContext          ← 每个 GSG 一份，持有 GL program 句柄
  (glShaderContext)
        │  bind() / issue_parameters() / update_shader_vertex_arrays()
        ▼
   OpenGL Driver         ← glUseProgram / glUniform* / glVertexAttribPointer
```

---

## 二、`Shader` 类核心数据结构

[`shader.h:51`](../panda/src/gobj/shader.h) 中 `Shader` 继承自 `TypedWritableReferenceCount`，支持多种着色器语言：

```cpp
enum ShaderLanguage { SL_none, SL_Cg, SL_GLSL, SL_HLSL, SL_SPIR_V };
enum ShaderType {
    ST_vertex, ST_fragment, ST_geometry,
    ST_tess_control, ST_tess_evaluation, ST_compute
};
```

### 关键内部规格表（编译后填充）

| 规格表 | 类型 | 作用 |
|--------|------|------|
| `_mat_spec` | `pvector<ShaderMatSpec>` | 矩阵/变换 uniform 绑定规格 |
| `_tex_spec` | `pvector<ShaderTexSpec>` | 纹理采样器绑定规格 |
| `_var_spec` | `pvector<ShaderVarSpec>` | 顶点属性（attribute）绑定规格 |
| `_ptr_spec` | `pvector<ShaderPtrSpec>` | 用户自定义 uniform 指针规格 |

### `ShaderMatSpec` 结构

描述一个 uniform 矩阵的来源（[`shader.h:467`](../panda/src/gobj/shader.h)）：

```cpp
struct ShaderMatSpec {
    size_t _cache_offset[2];   // 在矩阵缓存中的偏移
    ShaderArgId    _id;        // uniform 位置（seqno = GL location）
    ShaderMatFunc  _func;      // SMF_compose / SMF_first 等
    ShaderMatInput _part[2];   // 来源坐标系（model/view/clip/world）
    ShaderMatPiece _piece;     // 取矩阵的哪一部分（整行/列/转置等）
    int            _dep;       // 依赖的状态位（SSD_transform 等）
};
```

### `ShaderStateDep` 依赖位掩码（[`shader.h:309`](../panda/src/gobj/shader.h)）

```cpp
SSD_transform    = 0x2002   // 模型变换改变
SSD_material     = 0x010    // 材质改变
SSD_light        = 0x080    // 光源改变
SSD_shaderinputs = 0x020    // 用户 ShaderInput 改变
SSD_frame        = 0x400    // 每帧更新
SSD_texture      = 0x1000   // 纹理改变
SSD_projection   = 0x800    // 投影矩阵改变
```

---

## 三、着色器加载与编译流程

### 3.1 用户侧加载

```python
# Python 侧
shader = Shader.load(Shader.SL_GLSL, vertex="v.glsl", fragment="f.glsl")
node.set_shader(shader)
```

对应 C++ [`Shader::load()`](../panda/src/gobj/shader.h)，将 GLSL 源码存入 `ShaderFile` 结构：

```cpp
class ShaderFile {
    bool   _separate;        // 是否分离式（顶点/片段分开）
    string _vertex;          // 顶点着色器源码
    string _fragment;        // 片段着色器源码
    string _geometry;        // 几何着色器源码
    string _tess_control;    // 细分控制着色器
    string _tess_evaluation; // 细分求值着色器
    string _compute;         // 计算着色器
};
```

### 3.2 GL 编译链接（`glsl_compile_and_link`）

[`glShaderContext_src.cxx:3317`](../panda/src/glstuff/glShaderContext_src.cxx) 中的完整流程：

```
1. glCreateProgram()                    → 创建 GL program 对象
2. 尝试加载预编译二进制（program binary）
3. 若无缓存，对每种 ShaderType 调用 glsl_compile_shader()：
   ├─ glCreateShader(GL_VERTEX_SHADER / GL_FRAGMENT_SHADER / ...)
   ├─ glShaderSource(handle, 1, &text, nullptr)
   ├─ glCompileShader(handle)
   ├─ glGetShaderiv(GL_COMPILE_STATUS) → 检查错误
   └─ glAttachShader(_glsl_program, handle)
4. 绑定固定 attribute 位置：
   ├─ glBindAttribLocation(0, "p3d_Vertex")   // 顶点位置
   ├─ glBindAttribLocation(2, "p3d_Normal")   // 法线
   └─ glBindAttribLocation(3, "p3d_Color")    // 颜色
5. glLinkProgram(_glsl_program)
6. 可选：glGetProgramBinary() 缓存编译结果
```

### 3.3 反射（Reflection）阶段

链接成功后，立即通过 GL 反射 API 分析 program：

**顶点属性反射** [`reflect_attribute()`](../panda/src/glstuff/glShaderContext_src.cxx)：

```
glGetProgramiv(GL_ACTIVE_ATTRIBUTES)
glGetActiveAttrib()      → 获取名称、类型、大小
glGetAttribLocation()    → 获取 location
→ 识别 p3d_ 前缀（p3d_Vertex/Normal/Color/MultiTexCoord 等）
→ 填充 _shader->_var_spec[]
```

**Uniform 反射** [`reflect_uniform()`](../panda/src/glstuff/glShaderContext_src.cxx)：

```
glGetProgramiv(GL_ACTIVE_UNIFORMS)
glGetActiveUniform()     → 获取名称、类型、大小
→ 解析 p3d_ 前缀 uniform（p3d_ModelViewProjectionMatrix 等）
→ 解析 Panda 简写（trans_model_to_clip 等）
→ 填充 _shader->_mat_spec[] / _tex_spec[]
```

---

## 四、每帧渲染时的参数传递

### 4.1 `bind()` — 激活着色器

[`glShaderContext_src.cxx:2201`](../panda/src/glstuff/glShaderContext_src.cxx)：

```cpp
void bind(GraphicsStateGuardian *gsg) {
    glValidateProgram(_glsl_program);   // 首次验证
    glUseProgram(_glsl_program);        // 激活 program
}
```

### 4.2 `set_state_and_transform()` — 脏位检测

[`glShaderContext_src.cxx:2244`](../panda/src/glstuff/glShaderContext_src.cxx) 通过比较新旧 `RenderState` 计算 `altered` 位掩码：

```cpp
if (_modelview_transform != modelview_transform)
    altered |= SSD_transform;
if (state_rs->get_attrib(LightAttrib) != target_rs->get_attrib(LightAttrib))
    altered |= SSD_light;
if (_shader_attrib != _glgsg->_target_shader)
    altered |= SSD_shaderinputs;
// ... 检测 material/fog/color/texture 等所有状态
if (altered != 0) issue_parameters(altered);
```

### 4.3 `issue_parameters()` — 上传 Uniform

[`glShaderContext_src.cxx:2341`](../panda/src/glstuff/glShaderContext_src.cxx) 是性能关键路径：

```cpp
// 只更新发生变化的 uniform
for (ShaderMatSpec &spec : _shader->_mat_spec) {
    if ((altered & spec._dep) == 0) continue;  // 跳过未变化的

    // 从矩阵缓存中取值
    const LVecBase4f *val = fetch_specified_value(spec, _mat_part_cache, ...);
    GLint p = spec._id._seqno;  // GL uniform location

    // 根据类型调用对应的 glUniform*
    switch (spec._piece) {
    case SMP_scalar:         glUniform1fv(p, 1, data);
    case SMP_vec4:           glUniform4fv(p, 1, data);
    case SMP_mat4_whole:     glUniformMatrix4fv(p, 1, GL_FALSE, data);
    case SMP_mat4_transpose: glUniformMatrix4fv(p, 1, GL_TRUE, data);
    case SMP_mat4_upper3x3:  // 提取左上 3x3 → glUniformMatrix3fv
    // ...
    }
}
```

### 4.4 `update_shader_vertex_arrays()` — 顶点属性绑定

[`glShaderContext_src.cxx:2504`](../panda/src/glstuff/glShaderContext_src.cxx) 将 `GeomVertexData` 中的数组绑定到着色器 attribute location：

```
对每个 ShaderVarSpec（来自 _var_spec）：
  → 找到对应的 GeomVertexArrayData
  → glBindBuffer(GL_ARRAY_BUFFER, vbo)
  → glVertexAttribPointer(location, ...)
  → glEnableVertexAttribArray(location)
```

---

## 五、`ShaderAttrib` — 渲染状态层

[`shaderAttrib.h:39`](../panda/src/pgraph/shaderAttrib.h) 继承自 `RenderAttrib`，是场景图与着色器系统的桥梁：

```cpp
class ShaderAttrib : public RenderAttrib {
    CPT(Shader) _shader;          // 指向 Shader 对象
    bool _auto_shader;            // 是否使用 AutoShader
    bool _has_shader;
    int  _flags;                  // F_hardware_skinning 等
    typedef pmap<const InternalName*, ShaderInput> Inputs;
    Inputs _inputs;               // 用户设置的 ShaderInput
};
```

`compose_impl()` 实现继承链合并：子节点的 `ShaderAttrib` 会覆盖父节点的，`_inputs` 会合并（子节点优先）。

### 用户 API 对应关系

```python
node.set_shader(shader)           # → ShaderAttrib::set_shader()
node.set_shader_input("k", val)   # → ShaderAttrib::set_shader_input()
node.set_shader_auto()            # → ShaderAttrib::set_shader_auto()
                                  #   → _auto_shader = true
```

### `ShaderAttrib` 标志位

```cpp
enum {
    F_disable_alpha_write = 1 << 0,  // 禁止写入颜色缓冲 alpha 通道
    F_subsume_alpha_test  = 1 << 1,  // 着色器内部处理 alpha 测试（TEXKILL）
    F_hardware_skinning   = 1 << 2,  // 需要预动画顶点（硬件蒙皮）
    F_shader_point_size   = 1 << 3,  // 着色器提供点大小
    F_hardware_instancing = 1 << 4,  // 需要实例列表
};
```

---

## 六、AutoShader（自动着色器生成）机制

### 6.1 触发条件

当 [`ShaderAttrib::auto_shader()`](../panda/src/pgraph/shaderAttrib.h) 返回 `true` 时，`GraphicsStateGuardian` 在渲染前调用 `ensure_generated_shader()`。

### 6.2 `ShaderGenerator::analyze_renderstate()`

[`shaderGenerator.cxx:228`](../panda/src/pgraphnodes/shaderGenerator.cxx) 分析当前 `RenderState`，构建 `ShaderKey`（缓存键）：

```
分析内容：
├─ 透明度/Alpha 测试模式
├─ 顶点颜色类型（flat/vertex/off）
├─ 材质标志（ambient/diffuse/specular/emission）
├─ 光源列表（AmbientLight/DirectionalLight/PointLight/Spotlight）
│   └─ 每个光源：是否投影阴影、是否有高光颜色
├─ 纹理阶段列表：
│   ├─ M_modulate / M_normal / M_height / M_gloss / M_glow
│   ├─ M_normal_height（视差贴图）
│   └─ M_metallic_roughness（PBR）
├─ 雾效、裁剪平面
└─ 辅助输出（AuxBitplane：法线/辉光缓冲）
```

### 6.3 着色器代码生成

根据 `ShaderKey` 动态拼接 GLSL/Cg 源码，生成包含：

- 光照计算（Phong/Blinn-Phong）
- 法线贴图（TBN 矩阵变换）
- 视差贴图（迭代步进）
- 阴影贴图采样（PCF 软阴影）
- 雾效混合
- Alpha 测试

生成的 `Shader` 对象被缓存，下次相同 `ShaderKey` 直接复用。

---

## 七、坐标系变换矩阵命名约定

Panda3D 的 GLSL 着色器支持特殊命名的 uniform，由 [`parse_and_set_short_hand_shader_vars()`](../panda/src/glstuff/glShaderContext_src.cxx) 解析：

| uniform 名称 | 含义 |
|---|---|
| `p3d_ModelViewProjectionMatrix` | MVP 矩阵（model→clip） |
| `p3d_ModelViewMatrix` | MV 矩阵（model→view） |
| `p3d_ProjectionMatrix` | 投影矩阵（view→clip） |
| `trans_model_to_world` | 模型→世界变换 |
| `trans_world_to_view` | 世界→视图变换 |
| `tpose_model_to_view` | MV 矩阵的转置（用于法线变换） |
| `row3_model_to_view` | MV 矩阵第3行（位置） |
| `mspos_XXX` | 节点 XXX 在模型空间的位置 |
| `mat_modelview` | 等价于 `trans_model_to_apiview` |
| `mat_projection` | 等价于 `trans_apiview_to_apiclip` |
| `mat_modelproj` | 等价于 `trans_model_to_apiclip` |

---

## 八、完整渲染一帧的调用链

```
CullTraverser::traverse()
  └─ 遍历场景图，收集 CullableObject
       └─ 若 auto_shader → ensure_generated_shader()
            └─ ShaderGenerator::synthesize_shader()
                 └─ analyze_renderstate() → ShaderKey
                 └─ generate_shader()     → Shader 对象（含 GLSL 源码）

GraphicsStateGuardian::draw()
  └─ 对每个 CullableObject：
       1. apply_state(RenderState)
            └─ ShaderAttrib → prepare_now() → glShaderContext 构造
                 └─ glsl_compile_and_link()   [首次：编译+链接]
                 └─ reflect_attribute()        [填充 _var_spec]
                 └─ reflect_uniform()          [填充 _mat_spec/_tex_spec]
       2. bind(gsg)
            └─ glUseProgram(_glsl_program)
       3. set_state_and_transform(rs, mv, cam, proj)
            └─ 计算 altered 位掩码（脏位检测）
            └─ issue_parameters(altered)
                 └─ glUniform*(location, data)  [只更新变化的]
       4. update_shader_vertex_arrays()
            └─ glVertexAttribPointer() × N
            └─ glEnableVertexAttribArray() × N
       5. update_shader_texture_bindings()
            └─ glActiveTexture(GL_TEXTURE0 + i)
            └─ glBindTexture(target, handle)
            └─ glUniform1i(sampler_location, i)
       6. glDrawElements() / glDrawArrays()
       7. unbind()
            └─ glUseProgram(0)
```

---

## 九、关键设计模式总结

| 设计点 | 实现方式 |
|--------|---------|
| **脏位优化** | `ShaderStateDep` 位掩码，只上传变化的 uniform |
| **矩阵缓存** | `_mat_part_cache[]` 避免重复计算变换矩阵 |
| **反射驱动** | 编译后通过 GL 反射 API 自动建立参数绑定表 |
| **状态继承** | `ShaderAttrib::compose_impl()` 合并场景图继承链 |
| **AutoShader 缓存** | `ShaderKey` 哈希，相同渲染状态复用已生成着色器 |
| **预编译缓存** | `glGetProgramBinary` / `glProgramBinary` 跨会话缓存 |
| **多语言支持** | `SL_GLSL` / `SL_Cg` / `SL_HLSL` / `SL_SPIR_V` 统一接口 |

---

## 十、实践示例

### 最简 GLSL 着色器

```glsl
// vertex.glsl
#version 330
uniform mat4 p3d_ModelViewProjectionMatrix;
in vec4 p3d_Vertex;
in vec2 p3d_MultiTexCoord0;
out vec2 texcoord;

void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    texcoord = p3d_MultiTexCoord0;
}
```

```glsl
// fragment.glsl
#version 330
uniform sampler2D p3d_Texture0;
in vec2 texcoord;
out vec4 fragColor;

void main() {
    fragColor = texture(p3d_Texture0, texcoord);
}
```

```python
# Python 加载
shader = Shader.load(Shader.SL_GLSL,
                     vertex="vertex.glsl",
                     fragment="fragment.glsl")
model.set_shader(shader)
model.set_shader_input("myColor", LVecBase4f(1, 0, 0, 1))
```

### 自定义 uniform 传递路径

```
Python: node.set_shader_input("myColor", vec4)
  → ShaderAttrib._inputs["myColor"] = ShaderInput(vec4)
  → 每帧 issue_parameters() 中：
      → 遍历 _shader->_ptr_spec
      → 找到名为 "myColor" 的 ShaderPtrSpec
      → glUniform4fv(location, 1, data)
```
