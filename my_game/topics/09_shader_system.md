# 专题09：Shader 系统

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

Shader（着色器）是现代 GPU 渲染管线的核心，它将固定功能管线（Fixed-Function Pipeline）替换为完全可编程的阶段。

| 挑战 | 描述 |
|------|------|
| **跨平台差异** | GLSL/HLSL/Metal 语法不同，坐标系约定不同 |
| **Uniform 管理** | 大量 Uniform 变量需要高效更新，避免冗余上传 |
| **变体爆炸** | 不同材质组合（有无法线贴图、阴影等）需要不同 Shader 变体 |
| **编译延迟** | Shader 编译在 GPU 驱动层进行，可能造成首帧卡顿 |
| **调试困难** | GPU 上运行，无法直接断点调试 |
| **自动 Shader** | 引擎需要根据场景状态自动生成合适的 Shader |

Panda3D 提供两种 Shader 使用方式：
1. **手动 Shader**：用户编写 GLSL/Cg 代码，完全控制渲染
2. **自动 Shader**（ShaderGenerator）：引擎根据材质、光照、阴影等状态自动生成

---

## 2. 数学原理

### 2.1 渲染方程

Shader 的核心是实现（近似）**渲染方程**（Rendering Equation）：

```
L_o(x, ω_o) = L_e(x, ω_o) + ∫_Ω f_r(x, ω_i, ω_o) L_i(x, ω_i) (n·ω_i) dω_i
```

其中：
- `L_o`：出射辐射率（最终颜色）
- `L_e`：自发光
- `f_r`：BRDF（双向反射分布函数）
- `L_i`：入射辐射率（光源）
- `n·ω_i`：Lambert 余弦项

**实时渲染的近似**：将积分离散化为有限光源求和：
```
L_o = L_e + Σ_i f_r(ω_i, ω_o) * L_i * max(n·ω_i, 0)
```

### 2.2 Phong/Blinn-Phong BRDF

**Phong 模型**：
```
f_r = k_d/π + k_s * (R·V)^n / (n·L)

其中：
  R = 2(n·L)n - L  （反射向量）
  k_d = 漫反射系数
  k_s = 高光系数
  n   = 高光指数（shininess）
```

**Blinn-Phong 模型**（更高效，用半程向量代替反射向量）：
```
H = normalize(L + V)  （半程向量）
f_r = k_d/π + k_s * (n·H)^n
```

### 2.3 PBR（基于物理的渲染）

现代游戏使用 **Cook-Torrance BRDF**：

```
f_r = f_d + f_s

漫反射项（Lambertian）：
  f_d = albedo / π

高光项（Cook-Torrance）：
  f_s = D(h) * F(v,h) * G(l,v,h) / (4 * (n·l) * (n·v))
```

**三个核心函数**：

**D（法线分布函数，NDF）**：描述微表面法线的统计分布
```
GGX/Trowbridge-Reitz：
D(h) = α² / (π * ((n·h)² * (α²-1) + 1)²)
其中 α = roughness²
```

**F（菲涅尔方程）**：描述光在不同角度的反射率
```
Schlick 近似：
F(v,h) = F0 + (1 - F0) * (1 - v·h)^5
其中 F0 = 基础反射率（金属=albedo，非金属≈0.04）
```

**G（几何遮蔽函数）**：描述微表面的自遮蔽
```
Smith GGX：
G(l,v,h) = G1(l) * G1(v)
G1(x) = (n·x) / ((n·x)(1-k) + k)
其中 k = α/2（直接光）或 k = α²/2（IBL）
```

### 2.4 坐标空间变换

Shader 中涉及多个坐标空间，需要正确的变换矩阵：

```
模型空间 (Model Space)
  ↓ p3d_ModelMatrix (M)
世界空间 (World Space)
  ↓ p3d_ViewMatrix (V)
视图空间 (View/Eye Space)
  ↓ p3d_ProjectionMatrix (P)
裁剪空间 (Clip Space)
  ↓ 透视除法
NDC 空间 (-1 to 1)
  ↓ 视口变换
屏幕空间 (Screen Space)
```

**Panda3D 的坐标系约定**：
- 右手坐标系，Y 轴朝前，Z 轴朝上（与 OpenGL 的 Y 朝上不同）
- 在 GLSL 中，Panda3D 会自动处理坐标系转换

### 2.5 法线变换

法线不能直接用模型矩阵变换（非均匀缩放会破坏法线方向）：

```
正确的法线变换矩阵：
N_matrix = transpose(inverse(M))

在 Shader 中：
vec3 world_normal = normalize(mat3(p3d_NormalMatrix) * normal);
```

其中 `p3d_NormalMatrix` 是 Panda3D 自动提供的法线变换矩阵。

---

## 3. 工程实践

### 3.1 Shader 编译流程

```
GLSL 源码（.vert/.frag）
  ↓ Shader::load() / Shader::make()
Shader 对象（CPU 端）
  ↓ 首次渲染时 / prepare()
ShaderContext（GPU 端）
  ↓ glCompileShader() + glLinkProgram()
OpenGL Program Object
  ↓ 渲染时
glUseProgram() + Uniform 更新
```

**Shader 缓存**：编译后的二进制可以缓存到磁盘（`set_cache_compiled_shader(true)`），避免重复编译。

### 3.2 Uniform 变量系统

Panda3D 的 Uniform 分两类：

**自动 Uniform**（引擎自动提供）：
```glsl
// 变换矩阵
uniform mat4 p3d_ModelViewProjectionMatrix;  // MVP 矩阵
uniform mat4 p3d_ModelMatrix;                // 模型矩阵
uniform mat4 p3d_ViewMatrix;                 // 视图矩阵
uniform mat4 p3d_ProjectionMatrix;           // 投影矩阵
uniform mat3 p3d_NormalMatrix;               // 法线矩阵

// 材质
uniform struct {
    vec4 ambient;
    vec4 diffuse;
    vec4 emission;
    vec3 specular;
    float shininess;
} p3d_Material;

// 光照
uniform struct p3d_LightSourceParameters {
    vec4 color;
    vec4 ambient;
    vec4 diffuse;
    vec4 specular;
    vec4 position;       // 世界空间位置（w=0 表示方向光）
    vec3 attenuation;    // 常数/线性/二次衰减
    // ... 聚光灯参数
} p3d_LightSource[NUM_LIGHTS];

// 时间
uniform float osg_FrameTime;    // 当前时间（秒）
uniform float osg_DeltaFrameTime; // 帧间隔
```

**手动 Uniform**（用户通过 `set_shader_input` 提供）：
```python
node.set_shader_input('my_color', LVecBase4f(1, 0, 0, 1))
node.set_shader_input('my_texture', tex)
node.set_shader_input('my_matrix', mat4)
```

### 3.3 ShaderGenerator 自动 Shader

当调用 `set_shader_auto()` 时，Panda3D 的 ShaderGenerator 根据当前 RenderState 自动生成 Shader：

```
ShaderGenerator::synthesize_shader(RenderState)
  ├── 分析 RenderState：
  │   ├── 有几个光源？哪些类型？
  │   ├── 有几个纹理？哪些 TextureStage 模式？
  │   ├── 是否有法线贴图？
  │   ├── 是否需要阴影？
  │   └── 是否有雾？
  ├── 生成 ShaderKey（唯一标识这种组合）
  ├── 查找缓存（相同 Key 复用已生成的 Shader）
  └── 若未缓存：动态拼接 GLSL 代码
```

**ShaderKey 的作用**：避免为相同状态组合重复生成 Shader。

### 3.4 Shader 变体管理

**问题**：不同材质组合（有无法线贴图、有无阴影、光源数量等）需要不同的 Shader 代码。

**解决方案**：

1. **预处理宏**（#define）：
```glsl
#ifdef HAS_NORMAL_MAP
    vec3 normal = texture(normal_map, texcoord).rgb * 2.0 - 1.0;
#else
    vec3 normal = v_normal;
#endif
```

2. **Uber Shader**：一个 Shader 处理所有情况，用 if/else 分支（性能较差）

3. **ShaderGenerator 动态生成**：Panda3D 的方式，根据状态生成最优 Shader

---

## 4. Panda3D 源码剖析

### 4.1 Shader 类结构

**文件**：[`shader.h`](panda/src/gobj/shader.h)

```cpp
// shader.h:51
class EXPCL_PANDA_GOBJ Shader : public TypedWritableReferenceCount {
public:
  // 支持的着色语言
  enum ShaderLanguage {
    SL_none,
    SL_Cg,     // NVIDIA Cg（已废弃）
    SL_GLSL,   // OpenGL Shading Language
    SL_HLSL,   // DirectX High Level Shading Language
    SL_SPIR_V, // Vulkan/OpenGL 4.6 二进制格式
  };

  // 着色器阶段
  enum ShaderType {
    ST_vertex,          // 顶点着色器
    ST_fragment,        // 片段着色器
    ST_geometry,        // 几何着色器
    ST_tess_control,    // 细分控制着色器
    ST_tess_evaluation, // 细分求值着色器
    ST_compute,         // 计算着色器
  };

  // 从文件加载（分离的 vert/frag 文件）
  static PT(Shader) load(ShaderLanguage lang,
                         const Filename &vertex,
                         const Filename &fragment,
                         const Filename &geometry = "",
                         const Filename &tess_control = "",
                         const Filename &tess_evaluation = "");

  // 从字符串创建（内联 Shader）
  static PT(Shader) make(ShaderLanguage lang,
                         std::string vertex,
                         std::string fragment,
                         std::string geometry = "",
                         std::string tess_control = "",
                         std::string tess_evaluation = "");

  // 计算着色器
  static PT(Shader) load_compute(ShaderLanguage lang, const Filename &fn);
  static PT(Shader) make_compute(ShaderLanguage lang, std::string body);

  // 缓存编译后的二进制
  bool get_cache_compiled_shader() const;
  void set_cache_compiled_shader(bool flag);

  // 准备（上传到 GPU）
  PT(AsyncFuture) prepare(PreparedGraphicsObjects *prepared_objects);
  ShaderContext *prepare_now(PreparedGraphicsObjects *prepared_objects,
                             GraphicsStateGuardianBase *gsg);
};
```

**ShaderMatInput 枚举**（自动 Uniform 类型）：

```cpp
// shader.h:124
enum ShaderMatInput {
  SMO_identity,           // 单位矩阵
  SMO_window_size,        // 窗口尺寸
  SMO_pixel_size,         // 像素尺寸
  SMO_world_to_view,      // 世界->视图矩阵
  SMO_view_to_world,      // 视图->世界矩阵
  SMO_model_to_view,      // 模型->视图矩阵（MV）
  SMO_view_to_model,      // 视图->模型矩阵
  SMO_apiview_to_apiclip, // 投影矩阵（P）
  SMO_apiclip_to_apiview, // 投影矩阵的逆
  SMO_frame_number,       // 帧编号
  SMO_frame_time,         // 当前时间
  SMO_frame_delta,        // 帧间隔
  SMO_attr_material,      // 材质属性
  SMO_attr_color,         // 节点颜色
  SMO_light_source_i,     // 第 i 个光源
  SMO_light_ambient,      // 环境光
  // ...
};
```

### 4.2 ShaderAttrib 着色器属性

**文件**：[`shaderAttrib.h`](panda/src/pgraph/shaderAttrib.h)

```cpp
// shaderAttrib.h:39
class EXPCL_PANDA_PGRAPH ShaderAttrib final : public RenderAttrib {
public:
  // 标志位
  enum {
    F_disable_alpha_write = 1 << 0,  // 禁止写入 Alpha 通道
    F_subsume_alpha_test  = 1 << 1,  // Shader 自己处理 Alpha 测试
    F_hardware_skinning   = 1 << 2,  // 使用 GPU 蒙皮
    F_shader_point_size   = 1 << 3,  // Shader 控制点大小
    F_hardware_instancing = 1 << 4,  // 使用 GPU 实例化
  };

  // 创建
  static CPT(RenderAttrib) make(const Shader *shader = nullptr, int priority = 0);
  static CPT(RenderAttrib) make_off();    // 禁用 Shader（使用固定管线）
  static CPT(RenderAttrib) make_default(); // 默认（自动 Shader）

  // 设置 Shader
  CPT(RenderAttrib) set_shader(const Shader *s, int priority=0) const;
  CPT(RenderAttrib) set_shader_auto(int priority=0) const;  // 自动生成

  // 设置 Shader 输入（Uniform）
  // 支持多种类型：Texture, NodePath, float, vec2/3/4, mat3/4, 数组
  CPT(RenderAttrib) set_shader_input(const ShaderInput &input) const;

  // 实例化渲染
  CPT(RenderAttrib) set_instance_count(int instance_count) const;

  // 查询
  bool has_shader() const;
  bool auto_shader() const;
  const ShaderInput &get_shader_input(const InternalName *id) const;
};
```

### 4.3 ShaderGenerator 自动生成

**文件**：[`shaderGenerator.h`](panda/src/pgraphnodes/shaderGenerator.h)

```cpp
// shaderGenerator.h:73
class EXPCL_PANDA_PGRAPHNODES ShaderGenerator : public TypedReferenceCount {
public:
  // 核心：根据 RenderState 生成 Shader
  virtual CPT(ShaderAttrib) synthesize_shader(const RenderState *rs,
                                               const GeomVertexAnimationSpec &anim);

  // ShaderKey：唯一标识一种 Shader 变体
  struct ShaderKey {
    // 纹理信息
    enum TextureFlags {
      TF_has_rgb       = 0x001,
      TF_has_alpha     = 0x002,
      TF_has_texscale  = 0x004,
      TF_has_texcolor  = 0x008,
      TF_has_texmat    = 0x010,
      TF_uses_color    = 0x020,
      TF_uses_primary_color = 0x040,
      TF_uses_last_saved_result = 0x080,
      TF_is_2d        = 0x100,
    };

    struct TextureInfo {
      CPT(InternalName) texcoord_name;
      const TextureStage *stage;
      const Texture *texture;
      int flags;
      int combine_rgb;
      int combine_alpha;
    };

    // 光源信息
    enum LightFlags {
      LF_has_shadows    = 0x01,
      LF_has_specular   = 0x02,
    };

    struct LightInfo {
      TypeHandle type;  // AmbientLight/DirectionalLight/PointLight/Spotlight
      int flags;
    };

    // Key 的组成
    pvector<TextureInfo> _textures;
    pvector<LightInfo>   _lights;
    int _fog_mode;
    bool _have_normal_map;
    bool _have_gloss_map;
    bool _have_glow_map;
    bool _have_ramp;
    bool _calc_primary_alpha;
    // ...
  };
};
```
## 5. 代码演示

### 5.1 Python：基本 Shader 使用

```python
from panda3d.core import Shader, ShaderAttrib

# 从文件加载 GLSL Shader
shader = Shader.load(Shader.SL_GLSL,
    vertex='shaders/basic.vert',
    fragment='shaders/basic.frag')

# 应用到节点
model.set_shader(shader)

# 设置 Shader 输入（Uniform）
model.set_shader_input('color', (1.0, 0.5, 0.0, 1.0))
model.set_shader_input('time', 0.0)

# 每帧更新时间
def update_shader(task):
    model.set_shader_input('time', task.time)
    return task.cont
base.taskMgr.add(update_shader, 'update_shader')

# 从字符串创建内联 Shader（适合简单效果）
vert_src = """
#version 330
uniform mat4 p3d_ModelViewProjectionMatrix;
in vec4 p3d_Vertex;
in vec2 p3d_MultiTexCoord0;
out vec2 texcoord;
void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    texcoord = p3d_MultiTexCoord0;
}
"""
frag_src = """
#version 330
uniform sampler2D p3d_Texture0;
in vec2 texcoord;
out vec4 fragColor;
void main() {
    fragColor = texture(p3d_Texture0, texcoord);
}
"""
inline_shader = Shader.make(Shader.SL_GLSL, vert_src, frag_src)
model.set_shader(inline_shader)
```

### 5.2 GLSL：Blinn-Phong 光照 Shader

```glsl
// blinn_phong.vert
#version 330

uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelViewMatrix;
uniform mat3 p3d_NormalMatrix;

in vec4 p3d_Vertex;
in vec3 p3d_Normal;
in vec2 p3d_MultiTexCoord0;

out vec3 v_position;   // 视图空间位置
out vec3 v_normal;     // 视图空间法线
out vec2 v_texcoord;

void main() {
    vec4 view_pos = p3d_ModelViewMatrix * p3d_Vertex;
    v_position = view_pos.xyz;
    v_normal   = normalize(p3d_NormalMatrix * p3d_Normal);
    v_texcoord = p3d_MultiTexCoord0;
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
}
```

```glsl
// blinn_phong.frag
#version 330

// Panda3D 自动提供的光源结构
struct p3d_LightSourceParameters {
    vec4 color;
    vec4 ambient;
    vec4 diffuse;
    vec4 specular;
    vec4 position;       // 视图空间，w=0 表示方向光
    vec3 attenuation;    // 常数/线性/二次
    float spotCosCutoff;
    float spotExponent;
    vec3 spotDirection;
};

uniform p3d_LightSourceParameters p3d_LightSource[4];
uniform int p3d_LightSourceCount;

uniform struct {
    vec4 ambient;
    vec4 diffuse;
    vec4 emission;
    vec3 specular;
    float shininess;
} p3d_Material;

uniform sampler2D p3d_Texture0;

in vec3 v_position;
in vec3 v_normal;
in vec2 v_texcoord;
out vec4 fragColor;

void main() {
    vec4 tex_color = texture(p3d_Texture0, v_texcoord);
    vec3 N = normalize(v_normal);
    vec3 V = normalize(-v_position);  // 视图空间中，相机在原点

    vec3 result = p3d_Material.emission.rgb;

    for (int i = 0; i < p3d_LightSourceCount; ++i) {
        vec3 L;
        float attenuation = 1.0;

        if (p3d_LightSource[i].position.w == 0.0) {
            // 方向光
            L = normalize(p3d_LightSource[i].position.xyz);
        } else {
            // 点光源
            vec3 light_vec = p3d_LightSource[i].position.xyz - v_position;
            float dist = length(light_vec);
            L = normalize(light_vec);
            vec3 att = p3d_LightSource[i].attenuation;
            attenuation = 1.0 / (att.x + att.y * dist + att.z * dist * dist);
        }

        // 漫反射
        float NdotL = max(dot(N, L), 0.0);
        vec3 diffuse = p3d_Material.diffuse.rgb * p3d_LightSource[i].diffuse.rgb * NdotL;

        // Blinn-Phong 高光
        vec3 H = normalize(L + V);
        float NdotH = max(dot(N, H), 0.0);
        vec3 specular = p3d_Material.specular * p3d_LightSource[i].specular.rgb
                      * pow(NdotH, p3d_Material.shininess);

        result += (diffuse + specular) * attenuation;
    }

    fragColor = vec4(result * tex_color.rgb, tex_color.a);
}
```

### 5.3 GLSL：PBR Shader（简化版）

```glsl
// pbr.frag
#version 330

const float PI = 3.14159265359;

uniform sampler2D albedo_map;
uniform sampler2D normal_map;
uniform sampler2D metallic_roughness_map;  // R=metallic, G=roughness

uniform vec3 light_pos;
uniform vec3 light_color;
uniform vec3 cam_pos;

in vec3 v_world_pos;
in vec3 v_world_normal;
in vec2 v_texcoord;
in mat3 v_TBN;  // 切线空间矩阵

out vec4 fragColor;

// GGX 法线分布函数
float DistributionGGX(vec3 N, vec3 H, float roughness) {
    float a = roughness * roughness;
    float a2 = a * a;
    float NdotH = max(dot(N, H), 0.0);
    float denom = NdotH * NdotH * (a2 - 1.0) + 1.0;
    return a2 / (PI * denom * denom);
}

// Smith 几何遮蔽
float GeometrySmith(float NdotV, float NdotL, float roughness) {
    float r = roughness + 1.0;
    float k = r * r / 8.0;
    float G1V = NdotV / (NdotV * (1.0 - k) + k);
    float G1L = NdotL / (NdotL * (1.0 - k) + k);
    return G1V * G1L;
}

// Schlick 菲涅尔近似
vec3 FresnelSchlick(float cosTheta, vec3 F0) {
    return F0 + (1.0 - F0) * pow(1.0 - cosTheta, 5.0);
}

void main() {
    // 采样贴图
    vec3 albedo = pow(texture(albedo_map, v_texcoord).rgb, vec3(2.2));  // sRGB -> linear
    vec2 mr = texture(metallic_roughness_map, v_texcoord).rg;
    float metallic  = mr.r;
    float roughness = mr.g;

    // 法线贴图
    vec3 N = texture(normal_map, v_texcoord).rgb * 2.0 - 1.0;
    N = normalize(v_TBN * N);

    vec3 V = normalize(cam_pos - v_world_pos);
    vec3 L = normalize(light_pos - v_world_pos);
    vec3 H = normalize(V + L);

    float NdotV = max(dot(N, V), 0.001);
    float NdotL = max(dot(N, L), 0.0);

    // 基础反射率：非金属 F0=0.04，金属 F0=albedo
    vec3 F0 = mix(vec3(0.04), albedo, metallic);

    // Cook-Torrance BRDF
    float D = DistributionGGX(N, H, roughness);
    float G = GeometrySmith(NdotV, NdotL, roughness);
    vec3  F = FresnelSchlick(max(dot(H, V), 0.0), F0);

    vec3 specular = D * G * F / (4.0 * NdotV * NdotL + 0.001);

    // 能量守恒：高光越强，漫反射越弱
    vec3 kD = (1.0 - F) * (1.0 - metallic);
    vec3 diffuse = kD * albedo / PI;

    // 最终颜色
    float dist = length(light_pos - v_world_pos);
    float attenuation = 1.0 / (dist * dist);
    vec3 radiance = light_color * attenuation;

    vec3 color = (diffuse + specular) * radiance * NdotL;

    // Gamma 校正
    color = color / (color + vec3(1.0));  // Reinhard tone mapping
    color = pow(color, vec3(1.0 / 2.2));  // linear -> sRGB

    fragColor = vec4(color, 1.0);
}
```

### 5.4 Python：自动 Shader（ShaderGenerator）

```python
# 启用自动 Shader（引擎根据材质/光照自动生成）
render.set_shader_auto()

# 或者只对特定节点启用
model.set_shader_auto()

# 启用特定自动 Shader 功能
from panda3d.core import Shader
model.set_shader_auto(
    Shader.AS_normal |   # 法线贴图
    Shader.AS_shadow     # 阴影
)

# 设置法线贴图（自动 Shader 会自动处理）
from panda3d.core import TextureStage
ts_normal = TextureStage('normal')
ts_normal.set_mode(TextureStage.M_normal)
model.set_texture(ts_normal, normal_tex)

# 设置高光贴图
ts_gloss = TextureStage('gloss')
ts_gloss.set_mode(TextureStage.M_gloss)
model.set_texture(ts_gloss, gloss_tex)

# 关闭自动 Shader（恢复固定管线）
model.set_shader_off()
```

### 5.5 Python：计算着色器（Compute Shader）

```python
from panda3d.core import Shader, ShaderBuffer, Texture

# 创建计算着色器
compute_shader = Shader.load_compute(Shader.SL_GLSL, 'shaders/particle.comp')

# 创建 SSBO（Shader Storage Buffer Object）
particle_count = 10000
particle_buffer = ShaderBuffer('particles',
                               particle_count * 4 * 4,  # 每粒子 4 个 float4
                               GeomEnums.UH_dynamic)

# 设置计算着色器输入
dummy_node = render.attach_new_node('compute_node')
dummy_node.set_shader(compute_shader)
dummy_node.set_shader_input('particles', particle_buffer)
dummy_node.set_shader_input('dt', 0.016)

# 执行计算（每帧）
def run_compute(task):
    dummy_node.set_shader_input('dt', globalClock.get_dt())
    # 分发计算工作组（每组 64 个线程）
    base.graphicsEngine.dispatch_compute(
        (particle_count // 64, 1, 1),
        dummy_node.get_attrib(ShaderAttrib),
        base.win.get_gsg()
    )
    return task.cont
```

### 5.6 GLSL：顶点动画 Shader

```glsl
// wave_animation.vert
#version 330

uniform mat4 p3d_ModelViewProjectionMatrix;
uniform float time;
uniform float wave_amplitude;
uniform float wave_frequency;

in vec4 p3d_Vertex;
in vec2 p3d_MultiTexCoord0;

out vec2 texcoord;

void main() {
    vec4 pos = p3d_Vertex;

    // 基于 XY 位置的波浪动画
    float wave = sin(pos.x * wave_frequency + time) *
                 cos(pos.y * wave_frequency * 0.7 + time * 1.3);
    pos.z += wave * wave_amplitude;

    gl_Position = p3d_ModelViewProjectionMatrix * pos;
    texcoord = p3d_MultiTexCoord0;
}
```

```python
# Python 端
wave_shader = Shader.load(Shader.SL_GLSL,
    vertex='shaders/wave_animation.vert',
    fragment='shaders/basic.frag')

water.set_shader(wave_shader)
water.set_shader_input('wave_amplitude', 0.5)
water.set_shader_input('wave_frequency', 2.0)

def update_wave(task):
    water.set_shader_input('time', task.time)
    return task.cont
base.taskMgr.add(update_wave, 'update_wave')
```

### 5.7 GLSL：后处理 Shader（全屏效果）

```glsl
// post_process.frag
#version 330

uniform sampler2D scene_texture;   // 场景颜色
uniform sampler2D depth_texture;   // 深度缓冲
uniform vec2 screen_size;
uniform float time;

in vec2 texcoord;
out vec4 fragColor;

// 重建世界空间位置（从深度）
float linearize_depth(float depth, float near, float far) {
    return (2.0 * near * far) / (far + near - depth * (far - near));
}

// 色调映射（ACES）
vec3 aces_tonemap(vec3 x) {
    float a = 2.51, b = 0.03, c = 2.43, d = 0.59, e = 0.14;
    return clamp((x*(a*x+b))/(x*(c*x+d)+e), 0.0, 1.0);
}

void main() {
    vec3 color = texture(scene_texture, texcoord).rgb;

    // 晕影效果
    vec2 uv = texcoord * 2.0 - 1.0;
    float vignette = 1.0 - dot(uv * 0.5, uv * 0.5);
    color *= vignette;

    // 色调映射 + Gamma 校正
    color = aces_tonemap(color);
    color = pow(color, vec3(1.0 / 2.2));

    fragColor = vec4(color, 1.0);
}
```

---

## 6. 性能优化

### 6.1 减少 Shader 切换

```python
# 错误：每个物体使用不同的 Shader 对象（即使代码相同）
for obj in objects:
    shader = Shader.load(Shader.SL_GLSL, 'v.vert', 'f.frag')  # 每次创建新对象！
    obj.set_shader(shader)

# 正确：共享同一个 Shader 对象
shared_shader = Shader.load(Shader.SL_GLSL, 'v.vert', 'f.frag')
for obj in objects:
    obj.set_shader(shared_shader)  # 所有对象共享，只编译一次
```

### 6.2 批量更新 Shader 输入

```python
from panda3d.core import ShaderInput

# 错误：逐个设置（每次都触发状态更新）
node.set_shader_input('color', color)
node.set_shader_input('roughness', roughness)
node.set_shader_input('metallic', metallic)

# 正确：批量设置
inputs = [
    ShaderInput('color', color),
    ShaderInput('roughness', roughness),
    ShaderInput('metallic', metallic),
]
node.set_shader_inputs(inputs)
```

### 6.3 使用 PTA（Pointer To Array）共享数据

```python
from panda3d.core import PTA_LVecBase4f, PTA_float

# PTA 允许多个节点共享同一块内存，修改一次即可更新所有节点
shared_colors = PTA_LVecBase4f.empty_array(100)

# 所有节点引用同一个 PTA
for i, obj in enumerate(objects):
    obj.set_shader_input('object_color', shared_colors)

# 每帧只需更新 PTA，所有节点自动获得新值
def update_colors(task):
    for i in range(100):
        shared_colors[i] = (sin(task.time + i), 0.5, 0.5, 1.0)
    return task.cont
```

### 6.4 Shader 预编译

```python
# 在加载屏幕时预编译所有 Shader，避免游戏中卡顿
def precompile_shaders():
    shaders = [
        Shader.load(Shader.SL_GLSL, 'shaders/pbr.vert', 'shaders/pbr.frag'),
        Shader.load(Shader.SL_GLSL, 'shaders/shadow.vert', 'shaders/shadow.frag'),
        Shader.load(Shader.SL_GLSL, 'shaders/particle.vert', 'shaders/particle.frag'),
    ]
    pgo = base.win.get_gsg().get_prepared_objects()
    for shader in shaders:
        shader.prepare(pgo)
    # 强制立即编译
    base.graphicsEngine.render_frame()
    print(f"预编译了 {len(shaders)} 个 Shader")
```

### 6.5 Shader 变体管理

```python
# 使用字典缓存不同配置的 Shader
class ShaderCache:
    def __init__(self):
        self._cache = {}

    def get_shader(self, has_normal_map=False, has_shadow=False, num_lights=1):
        key = (has_normal_map, has_shadow, num_lights)
        if key not in self._cache:
            # 根据配置生成 #define 宏
            defines = f"""
#define NUM_LIGHTS {num_lights}
{'#define HAS_NORMAL_MAP' if has_normal_map else ''}
{'#define HAS_SHADOW' if has_shadow else ''}
"""
            # 将 defines 注入到 Shader 源码开头
            vert_src = defines + open('shaders/pbr.vert').read()
            frag_src = defines + open('shaders/pbr.frag').read()
            self._cache[key] = Shader.make(Shader.SL_GLSL, vert_src, frag_src)
        return self._cache[key]

shader_cache = ShaderCache()
model.set_shader(shader_cache.get_shader(has_normal_map=True, num_lights=3))
```

### 6.6 性能对比

| 技术 | Draw Call 开销 | 适用场景 |
|------|--------------|---------|
| 固定管线 | 低 | 简单场景，兼容性优先 |
| 自动 Shader | 中 | 快速开发，标准光照 |
| 手动 GLSL | 低（优化后） | 自定义效果，性能关键 |
| Compute Shader | 极低（GPU 并行） | 粒子、物理、后处理 |

---

## 小结

| 知识点 | 核心要点 |
|--------|---------|
| **渲染方程** | L_o = L_e + 积分(BRDF * L_i * cos) |
| **Blinn-Phong** | 半程向量代替反射向量；漫反射+高光+环境光 |
| **PBR** | D(NDF) * F(菲涅尔) * G(几何遮蔽) / 4(n·l)(n·v) |
| **坐标空间** | 模型->世界->视图->裁剪->NDC->屏幕 |
| **法线变换** | 使用 transpose(inverse(M))，即 p3d_NormalMatrix |
| **自动 Uniform** | p3d_ModelViewProjectionMatrix 等由引擎自动提供 |
| **ShaderGenerator** | 根据 RenderState 动态生成最优 Shader 变体 |
| **ShaderKey** | 唯一标识 Shader 变体，避免重复生成 |
| **PTA** | 多节点共享 Uniform 数据，一次修改全部生效 |
| **预编译** | 加载时预编译 Shader，避免游戏中卡顿 |

**Panda3D Shader 系统的设计哲学**：
- 渐进式：从自动 Shader 到完全手动，灵活选择控制级别
- 自动绑定：p3d_ 前缀的 Uniform 自动从场景状态获取
- 跨平台：GLSL/Cg/HLSL 多语言支持，统一的 Python API
- 可扩展：ShaderGenerator 可以被子类化，实现自定义自动 Shader
