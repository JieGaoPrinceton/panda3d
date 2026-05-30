# 专题04：光照与阴影

## 目录
1. [问题背景](#1-问题背景)
2. [数学原理](#2-数学原理)
   - 2.1 光照模型：Phong/Blinn-Phong
   - 2.2 Shadow Map 原理
   - 2.3 PCF 软阴影
   - 2.4 级联阴影贴图（CSM）
3. [工程实践](#3-工程实践)
   - 3.1 光照类型与继承体系
   - 3.2 LightAttrib 与光照绑定
   - 3.3 阴影贴图渲染流程
   - 3.4 ShaderGenerator 自动生成光照 Shader
4. [Panda3D 源码解析](#4-panda3d-源码解析)
   - 4.1 Light 基类与 LightLensNode
   - 4.2 DirectionalLight 阴影设置
   - 4.3 ShaderGenerator::ShaderKey 光照信息
5. [代码演示](#5-代码演示)
6. [性能分析](#6-性能分析)

---

## 1. 问题背景

光照与阴影是 3D 渲染中最复杂的问题之一：

1. **光照计算**：每个像素需要对所有光源求和，代价随光源数量线性增长
2. **阴影**：判断一个点是否被遮挡，需要从光源视角渲染整个场景
3. **软阴影**：真实阴影边缘是模糊的（半影区），需要多次采样
4. **全局光照**：光线在场景中多次反弹，实时计算极其昂贵

Panda3D 提供了从固定管线光照到自动 Shader 生成的完整解决方案。

---

## 2. 数学原理

### 2.1 光照模型：Phong/Blinn-Phong

**Phong 光照模型**将光照分为三个分量：

$$L = L_{ambient} + L_{diffuse} + L_{specular}$$

**环境光（Ambient）**：
$$L_{ambient} = k_a \cdot I_a$$

**漫反射（Diffuse）**：基于 Lambert 余弦定律
$$L_{diffuse} = k_d \cdot I_d \cdot \max(\mathbf{n} \cdot \mathbf{l}, 0)$$

其中：
- $\mathbf{n}$：表面法向量（单位向量）
- $\mathbf{l}$：指向光源的方向向量（单位向量）
- $k_d$：漫反射系数（材质颜色）
- $I_d$：光源漫反射强度

**镜面反射（Specular）**：
- Phong 模型：$L_{spec} = k_s \cdot I_s \cdot \max(\mathbf{r} \cdot \mathbf{v}, 0)^n$
  - $\mathbf{r} = 2(\mathbf{n} \cdot \mathbf{l})\mathbf{n} - \mathbf{l}$：反射向量
  - $\mathbf{v}$：指向观察者的方向
- **Blinn-Phong 模型**（更高效）：$L_{spec} = k_s \cdot I_s \cdot \max(\mathbf{n} \cdot \mathbf{h}, 0)^n$
  - $\mathbf{h} = \frac{\mathbf{l} + \mathbf{v}}{|\mathbf{l} + \mathbf{v}|}$：半程向量（Half Vector）

**点光源衰减**：
$$\text{attenuation} = \frac{1}{k_c + k_l \cdot d + k_q \cdot d^2}$$

其中 $d$ 是到光源的距离，$k_c, k_l, k_q$ 分别是常数、线性、二次衰减系数。

**聚光灯（Spotlight）**：
$$\text{spot\_factor} = \max(\mathbf{l}_{dir} \cdot (-\mathbf{l}), 0)^{e}$$

其中 $\mathbf{l}_{dir}$ 是聚光灯方向，$e$ 是聚光指数（控制光锥锐度）。

### 2.2 Shadow Map 原理

**Shadow Map** 是最常用的实时阴影技术：

**第一步：从光源视角渲染深度图**

将相机放在光源位置，渲染场景，只记录每个像素的深度值（距离光源的距离）。

$$\text{shadow\_map}[u, v] = \min_{(x,y,z) \to (u,v)} \frac{z - z_{near}}{z_{far} - z_{near}}$$

**第二步：在主渲染中判断遮挡**

对于每个片段 $P$，将其变换到光源的裁剪空间：

$$P_{light} = M_{proj\_light} \cdot M_{view\_light} \cdot P_{world}$$

归一化到 $[0,1]^3$：

$$u = \frac{P_{light}.x}{P_{light}.w} \cdot 0.5 + 0.5$$
$$v = \frac{P_{light}.y}{P_{light}.w} \cdot 0.5 + 0.5$$
$$z_{current} = \frac{P_{light}.z}{P_{light}.w} \cdot 0.5 + 0.5$$

**遮挡判断**：

$$\text{in\_shadow} = (z_{current} > \text{shadow\_map}[u, v] + \text{bias})$$

**深度偏移（Depth Bias）**：防止自遮挡（Shadow Acne）：

$$\text{bias} = \max(0.05 \cdot (1 - \mathbf{n} \cdot \mathbf{l}), 0.005)$$

### 2.3 PCF 软阴影

**PCF（Percentage Closer Filtering）** 通过对 Shadow Map 周围多个采样点取平均，产生软阴影效果：

$$\text{shadow} = \frac{1}{N} \sum_{i=1}^{N} \text{compare}(z_{current}, \text{shadow\_map}[u + \delta u_i, v + \delta v_i])$$

常用采样模式：
- **2×2 PCF**：4 次采样，轻微软化
- **3×3 PCF**：9 次采样，中等软化
- **Poisson Disk PCF**：随机分布采样，更自然

**PCSS（Percentage Closer Soft Shadows）**：根据遮挡物距离动态调整 PCF 核大小，模拟真实半影。

### 2.4 级联阴影贴图（CSM）

**问题**：单张 Shadow Map 无法同时覆盖近处（需要高精度）和远处（需要大范围）。

**CSM 解决方案**：将视锥体分割为多个子视锥体，每个子视锥体使用独立的 Shadow Map：

$$\text{split}_i = \lambda \cdot z_{near} \cdot \left(\frac{z_{far}}{z_{near}}\right)^{i/N} + (1-\lambda) \cdot \left(z_{near} + \frac{i}{N}(z_{far} - z_{near})\right)$$

其中 $\lambda$ 控制对数分割和均匀分割的混合比例。

**典型配置**：
- 级联 0：0-10m，Shadow Map 1024×1024
- 级联 1：10-50m，Shadow Map 1024×1024
- 级联 2：50-200m，Shadow Map 1024×1024
- 级联 3：200-1000m，Shadow Map 512×512

---

## 3. 工程实践

### 3.1 光照类型与继承体系

```
Light（抽象基类）
├── AmbientLight          — 环境光，无方向，均匀照亮所有表面
├── LightNode             — 有位置的光源基类
│   └── PointLight        — 点光源，向所有方向发光
└── LightLensNode         — 继承自 Light + Camera（用于阴影）
    ├── DirectionalLight  — 平行光（如太阳），无衰减
    ├── Spotlight         — 聚光灯，有方向和锥角
    ├── RectangleLight    — 矩形面光源
    └── SphereLight       — 球形面光源
```

**LightLensNode 的双重身份**：
- 作为 `Light`：提供光照参数（颜色、强度、衰减）
- 作为 `Camera`：从光源视角渲染 Shadow Map

### 3.2 LightAttrib 与光照绑定

光照通过 `LightAttrib` 附加到节点，影响该节点及其子树：

```
render.set_light(sun_np)
    ↓
LightAttrib 被添加到 render 的 RenderState
    ↓
CullTraverser 遍历时，LightAttrib 随 RenderState 向下传播
    ↓
每个 GeomNode 的 CullableObject 携带包含光照信息的 RenderState
    ↓
GSG.set_state_and_transform() 绑定光照 Uniform
    ↓
Shader 中使用光照参数计算光照
```

### 3.3 阴影贴图渲染流程

```
1. 调用 light.set_shadow_caster(True, 1024, 1024)
   ↓
2. LightLensNode 创建离屏缓冲区（GraphicsOutput）
   ↓
3. 每帧，GraphicsEngine 先渲染阴影缓冲区：
   - 使用光源的 Camera（LightLensNode 继承自 Camera）
   - 只渲染深度，不渲染颜色
   ↓
4. 阴影贴图（Texture）绑定到主渲染的 Shader
   ↓
5. 主渲染中，Shader 采样阴影贴图判断遮挡
```

### 3.4 ShaderGenerator 自动生成光照 Shader

Panda3D 的 `ShaderGenerator` 根据 `RenderState` 自动生成 GLSL/Cg Shader：

```
render.set_shader_auto()
    ↓
ShaderGenerator.synthesize_shader(render_state, anim_spec)
    ↓
analyze_renderstate() 分析：
  - 有哪些光源类型（Directional/Point/Spot）
  - 是否有阴影（LF_has_shadows）
  - 是否有法线贴图（TF_map_normal）
  - 是否有高光贴图（TF_map_gloss）
    ↓
根据 ShaderKey 生成对应的 GLSL 代码
    ↓
缓存到 _generated_shaders（相同 Key 复用）
```

---

## 4. Panda3D 源码解析

### 4.1 Light 基类与 LightLensNode

**文件**：[`panda/src/pgraph/light.h`](../../panda/src/pgraph/light.h)

```cpp
// light.h:38
class EXPCL_PANDA_PGRAPH Light {
PUBLISHED:
  // 光源颜色（RGBA）
  INLINE const LColor &get_color() const;
  INLINE void set_color(const LColor &color);

  // 色温（开尔文），自动转换为 RGB 颜色
  INLINE bool has_color_temperature() const;
  void set_color_temperature(PN_stdfloat temperature);

  // 镜面反射颜色（可与漫反射颜色不同）
  virtual const LColor &get_specular_color() const;

  // 衰减系数（常数、线性、二次）
  virtual const LVecBase3 &get_attenuation() const;

  // 优先级（当光源数量超过 GPU 限制时，低优先级光源被丢弃）
  INLINE void set_priority(int priority);
  INLINE int get_priority() const;

  // 光源类型优先级（内部使用）
  enum ClassPriority {
    CP_ambient_priority,      // 最低
    CP_point_priority,
    CP_directional_priority,
    CP_spot_priority,
    CP_area_priority,         // 最高
  };

public:
  // 将光源参数绑定到 GSG（纯虚函数，各子类实现）
  virtual void bind(GraphicsStateGuardianBase *gsg,
                    const NodePath &light, int light_id) = 0;
};
```

**文件**：[`panda/src/pgraphnodes/lightLensNode.h`](../../panda/src/pgraphnodes/lightLensNode.h)

```cpp
// lightLensNode.h:33
// LightLensNode 同时继承 Light 和 Camera
// Camera 部分用于从光源视角渲染 Shadow Map
class EXPCL_PANDA_PGRAPHNODES LightLensNode : public Light, public Camera {
PUBLISHED:
  // 启用/禁用阴影投射
  INLINE bool is_shadow_caster() const;
  void set_shadow_caster(bool caster);
  void set_shadow_caster(bool caster, int buffer_xsize, int buffer_ysize,
                         int sort = -10);

  // Shadow Map 缓冲区大小
  INLINE LVecBase2i get_shadow_buffer_size() const;
  INLINE void set_shadow_buffer_size(const LVecBase2i &size);

  // 获取对应 GSG 的 Shadow Map 缓冲区
  INLINE GraphicsOutputBase *get_shadow_buffer(GraphicsStateGuardianBase *gsg);

protected:
  LVecBase2i _sb_size;      // Shadow Map 分辨率
  bool _shadow_caster;      // 是否投射阴影
  PT(Texture) _shadow_map;  // 阴影贴图纹理

  // 每个 GSG 对应一个离屏缓冲区（支持多窗口）
  typedef pmap<PT(GraphicsStateGuardianBase),
               PT(GraphicsOutputBase)> ShadowBuffers;
  ShadowBuffers _sbuffers;
};
```

### 4.2 DirectionalLight 阴影设置

**文件**：[`panda/src/pgraphnodes/directionalLight.h`](../../panda/src/pgraphnodes/directionalLight.h)

```cpp
// directionalLight.h:25
class EXPCL_PANDA_PGRAPHNODES DirectionalLight : public LightLensNode {
PUBLISHED:
  // 镜面反射颜色（可独立于漫反射颜色）
  INLINE const LColor &get_specular_color() const final;
  INLINE void set_specular_color(const LColor &color);

  // 光源方向（在光源局部坐标系中）
  INLINE const LVector3 &get_direction() const;
  INLINE void set_direction(const LVector3 &direction);

public:
  // 将光源方向向量变换到物体局部空间
  virtual bool get_vector_to_light(LVector3 &result,
                                   const LPoint3 &from_object_point,
                                   const LMatrix4 &to_object_space);

  // 绑定到 GSG（设置 OpenGL 光源参数）
  virtual void bind(GraphicsStateGuardianBase *gsg,
                    const NodePath &light, int light_id);
};
```

### 4.3 ShaderGenerator::ShaderKey 光照信息

**文件**：[`panda/src/pgraphnodes/shaderGenerator.h`](../../panda/src/pgraphnodes/shaderGenerator.h)

```cpp
// shaderGenerator.h:96
struct ShaderKey {
  // 光照标志
  enum LightFlags {
    LF_has_shadows = 1,          // 该光源投射阴影
    LF_has_specular_color = 2,   // 该光源有独立镜面反射颜色
  };

  // 每个光源的信息
  struct LightInfo {
    TypeHandle _type;   // 光源类型（DirectionalLight, PointLight, etc.）
    int _flags;         // LightFlags 组合
  };
  pvector<LightInfo> _lights;  // 所有激活的光源列表

  bool _lighting;              // 是否启用光照
  bool _have_separate_ambient; // 是否有独立的环境光

  // 纹理贴图标志
  enum TextureFlags {
    TF_map_normal   = 0x020,  // 法线贴图
    TF_map_height   = 0x040,  // 高度贴图（视差映射）
    TF_map_glow     = 0x080,  // 自发光贴图
    TF_map_gloss    = 0x100,  // 高光贴图
    TF_map_emission = 0x001000000,   // 自发光贴图（PBR）
    TF_map_occlusion = 0x002000000,  // 遮蔽贴图（AO）
  };
};

// synthesize_shader() 根据 ShaderKey 生成对应的 GLSL 代码
// 相同 ShaderKey 的 Shader 会被缓存复用
typedef phash_map<ShaderKey, CPT(ShaderAttrib)> GeneratedShaders;
GeneratedShaders _generated_shaders;
```

---

## 5. 代码演示

### 5.1 Python：基本光照设置

```python
from panda3d.core import (
    AmbientLight, DirectionalLight, PointLight, Spotlight,
    LColor, LVector3, LPoint3, NodePath
)

# ── 环境光 ───────────────────────────────────────────────────────────────────
ambient = AmbientLight("ambient")
ambient.set_color(LColor(0.2, 0.2, 0.2, 1))  # 低强度白色环境光
ambient_np = render.attach_new_node(ambient)
render.set_light(ambient_np)

# ── 平行光（太阳光）─────────────────────────────────────────────────────────
sun = DirectionalLight("sun")
sun.set_color(LColor(1.0, 0.95, 0.8, 1))  # 暖白色
sun.set_direction(LVector3(-1, -1, -2))    # 从右上方照射
sun_np = render.attach_new_node(sun)
render.set_light(sun_np)

# ── 点光源 ───────────────────────────────────────────────────────────────────
point = PointLight("point_light")
point.set_color(LColor(1, 0.5, 0, 1))  # 橙色
# 设置衰减：(常数, 线性, 二次)
point.set_attenuation(LVector3(1, 0.1, 0.01))
point_np = render.attach_new_node(point)
point_np.set_pos(0, 0, 5)  # 放置在场景中
render.set_light(point_np)

# ── 聚光灯 ───────────────────────────────────────────────────────────────────
spot = Spotlight("spotlight")
spot.set_color(LColor(1, 1, 1, 1))
spot.set_exponent(40)  # 聚光指数（越大越集中）
# 设置聚光角度
from panda3d.core import PerspectiveLens
lens = PerspectiveLens()
lens.set_fov(30)  # 30 度视角
spot.set_lens(lens)
spot_np = render.attach_new_node(spot)
spot_np.set_pos(0, -10, 10)
spot_np.look_at(0, 0, 0)  # 指向原点
render.set_light(spot_np)

# ── 局部光照（只影响特定节点）───────────────────────────────────────────────
# 只让 room 节点受到 room_light 的影响
room = render.attach_new_node("room")
room_light = PointLight("room_light")
room_light_np = room.attach_new_node(room_light)
room.set_light(room_light_np)  # 只影响 room 及其子节点

# 关闭某个节点的光照
some_node.set_light_off()  # 关闭所有光照
some_node.set_light_off(sun_np)  # 只关闭太阳光
```

### 5.2 Python：阴影设置

```python
from panda3d.core import DirectionalLight, LColor, LVector3

# ── 启用阴影 ─────────────────────────────────────────────────────────────────
sun = DirectionalLight("sun")
sun.set_color(LColor(1, 1, 1, 1))

# 启用阴影投射，设置 Shadow Map 分辨率
sun.set_shadow_caster(True, 2048, 2048)

# 调整阴影相机的视锥体（覆盖整个场景）
sun.get_lens().set_near_far(1, 500)
sun.get_lens().set_film_size(200, 200)  # 正交投影范围

sun_np = render.attach_new_node(sun)
sun_np.set_hpr(45, -45, 0)  # 设置光源方向
render.set_light(sun_np)

# 启用自动 Shader（包含阴影计算）
render.set_shader_auto()

# ── 调整阴影质量 ─────────────────────────────────────────────────────────────
# 更大的 Shadow Map = 更清晰的阴影（但更耗内存）
sun.set_shadow_caster(True, 4096, 4096)

# 调整深度偏移（防止 Shadow Acne）
# 通过 Shader 输入设置
render.set_shader_input("shadow_bias", 0.005)

# ── 聚光灯阴影 ───────────────────────────────────────────────────────────────
spot = Spotlight("spot")
spot.set_shadow_caster(True, 1024, 1024)
spot_np = render.attach_new_node(spot)
spot_np.set_pos(0, -10, 10)
spot_np.look_at(0, 0, 0)
render.set_light(spot_np)
render.set_shader_auto()
```

### 5.3 Python：自定义光照 Shader

```python
from panda3d.core import Shader, NodePath

# ── 自定义 Blinn-Phong 光照 Shader ──────────────────────────────────────────
vert_shader = """
#version 330

uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelMatrix;
uniform mat3 p3d_NormalMatrix;

in vec4 p3d_Vertex;
in vec3 p3d_Normal;
in vec2 p3d_MultiTexCoord0;

out vec3 v_world_pos;
out vec3 v_normal;
out vec2 v_texcoord;

void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    v_world_pos = (p3d_ModelMatrix * p3d_Vertex).xyz;
    v_normal = normalize(p3d_NormalMatrix * p3d_Normal);
    v_texcoord = p3d_MultiTexCoord0;
}
"""

frag_shader = """
#version 330

// Panda3D 自动提供的光照 Uniform
struct p3d_LightSourceParameters {
    vec4 color;
    vec4 position;       // w=0 表示平行光，w=1 表示点光源
    vec3 attenuation;    // (常数, 线性, 二次)
    vec3 spotDirection;
    float spotExponent;
    float spotCosCutoff;
};

uniform p3d_LightSourceParameters p3d_LightSource[4];
uniform vec4 p3d_LightModel.ambient;

uniform sampler2D p3d_Texture0;
uniform vec3 camera_pos;

in vec3 v_world_pos;
in vec3 v_normal;
in vec2 v_texcoord;

out vec4 frag_color;

void main() {
    vec3 N = normalize(v_normal);
    vec3 V = normalize(camera_pos - v_world_pos);
    vec4 base_color = texture(p3d_Texture0, v_texcoord);

    // 环境光
    vec3 ambient = p3d_LightModel.ambient.rgb * base_color.rgb;
    vec3 diffuse = vec3(0.0);
    vec3 specular = vec3(0.0);

    for (int i = 0; i < 4; i++) {
        vec3 L;
        float attenuation = 1.0;

        if (p3d_LightSource[i].position.w == 0.0) {
            // 平行光
            L = normalize(-p3d_LightSource[i].position.xyz);
        } else {
            // 点光源
            vec3 light_vec = p3d_LightSource[i].position.xyz - v_world_pos;
            float dist = length(light_vec);
            L = normalize(light_vec);
            vec3 att = p3d_LightSource[i].attenuation;
            attenuation = 1.0 / (att.x + att.y * dist + att.z * dist * dist);
        }

        // Blinn-Phong 漫反射
        float NdotL = max(dot(N, L), 0.0);
        diffuse += p3d_LightSource[i].color.rgb * base_color.rgb
                   * NdotL * attenuation;

        // Blinn-Phong 镜面反射
        if (NdotL > 0.0) {
            vec3 H = normalize(L + V);  // 半程向量
            float NdotH = max(dot(N, H), 0.0);
            specular += p3d_LightSource[i].color.rgb
                        * pow(NdotH, 64.0) * attenuation;
        }
    }

    frag_color = vec4(ambient + diffuse + specular * 0.5, base_color.a);
}
"""

shader = Shader.make(Shader.SL_GLSL, vert_shader, frag_shader)
render.set_shader(shader)
render.set_shader_input("camera_pos", base.camera.get_pos(render))
```

### 5.4 Python：PCF 软阴影 Shader

```python
# PCF 软阴影片段着色器（关键部分）
pcf_shadow_frag = """
#version 330

uniform sampler2DShadow p3d_Texture1;  // 阴影贴图（深度比较纹理）
uniform mat4 shadow_mvp;               // 光源的 MVP 矩阵

in vec3 v_world_pos;
in vec3 v_normal;

out vec4 frag_color;

// PCF 采样偏移（3×3 核）
const vec2 pcf_offsets[9] = vec2[](
    vec2(-1,-1), vec2(0,-1), vec2(1,-1),
    vec2(-1, 0), vec2(0, 0), vec2(1, 0),
    vec2(-1, 1), vec2(0, 1), vec2(1, 1)
);

float compute_shadow(vec3 world_pos, vec3 normal, vec3 light_dir) {
    // 将世界坐标变换到光源裁剪空间
    vec4 light_space_pos = shadow_mvp * vec4(world_pos, 1.0);
    vec3 proj_coords = light_space_pos.xyz / light_space_pos.w;
    proj_coords = proj_coords * 0.5 + 0.5;  // 变换到 [0,1]

    // 超出阴影贴图范围的区域不在阴影中
    if (proj_coords.z > 1.0) return 1.0;

    // 自适应深度偏移（根据法线与光线夹角）
    float bias = max(0.005 * (1.0 - dot(normal, light_dir)), 0.001);

    // PCF：对 3×3 邻域采样取平均
    float shadow = 0.0;
    vec2 texel_size = 1.0 / textureSize(p3d_Texture1, 0);
    for (int i = 0; i < 9; i++) {
        vec3 sample_coord = vec3(
            proj_coords.xy + pcf_offsets[i] * texel_size,
            proj_coords.z - bias
        );
        // sampler2DShadow 自动做深度比较，返回 0.0 或 1.0
        shadow += texture(p3d_Texture1, sample_coord);
    }
    return shadow / 9.0;  // 平均值即为光照比例
}

void main() {
    vec3 N = normalize(v_normal);
    vec3 L = normalize(vec3(1, 1, 2));  // 平行光方向

    float shadow_factor = compute_shadow(v_world_pos, N, L);
    float NdotL = max(dot(N, L), 0.0);

    vec3 color = vec3(0.8) * NdotL * shadow_factor + vec3(0.1);
    frag_color = vec4(color, 1.0);
}
"""

# Python 端设置
shader = Shader.make(Shader.SL_GLSL, vert_shader, pcf_shadow_frag)
render.set_shader(shader)
render.set_shader_input("shadow_mvp", sun_np.get_mat(render))
```

---

## 6. 性能分析

### 6.1 光照计算代价

| 光源类型 | 每像素计算量 | 阴影代价 |
|----------|------------|---------|
| AmbientLight | O(1) | 无 |
| DirectionalLight | ~10 ops | 1次纹理采样（硬阴影）/ 9次（PCF） |
| PointLight | ~15 ops（含衰减） | 6面 Cube Shadow Map |
| Spotlight | ~20 ops（含聚光） | 1次纹理采样 |

### 6.2 Shadow Map 分辨率 vs 质量

| 分辨率 | 内存 | 阴影质量 | 适用场景 |
|--------|------|---------|---------|
| 512×512 | 1 MB | 低（明显锯齿） | 远处阴影、移动端 |
| 1024×1024 | 4 MB | 中 | 一般场景 |
| 2048×2048 | 16 MB | 高 | 主要光源 |
| 4096×4096 | 64 MB | 极高 | 离线渲染 |

### 6.3 常见性能陷阱

```python
# ❌ 错误：过多动态光源
for i in range(20):
    light = PointLight(f"light_{i}")
    render.set_light(render.attach_new_node(light))
# 问题：每个光源都需要在 Shader 中循环计算，GPU 代价线性增长

# ✅ 正确：限制动态光源数量，使用光照贴图烘焙静态光照
# 动态光源：最多 4-8 个
# 静态光照：烘焙到 Lightmap 纹理

# ❌ 错误：所有光源都启用阴影
for light in all_lights:
    light.set_shadow_caster(True, 2048, 2048)
# 问题：每个阴影光源需要额外渲染一遍场景

# ✅ 正确：只有主要光源投射阴影
sun.set_shadow_caster(True, 2048, 2048)   # 主光源：高质量阴影
fill.set_shadow_caster(False)              # 补光：无阴影

# ❌ 错误：Shadow Map 分辨率过高
sun.set_shadow_caster(True, 8192, 8192)   # 256 MB！

# ✅ 正确：根据场景大小选择合适分辨率
# 小场景（<100m）：1024×1024
# 中等场景（<500m）：2048×2048
# 大场景：使用 CSM（级联阴影）

# ── 优化：使用 set_shader_auto() 而非手写 Shader ──────────────────────────
# Panda3D 的 ShaderGenerator 会根据实际使用的光源类型生成最优 Shader
# 避免在 Shader 中循环处理未使用的光源类型
render.set_shader_auto()
```

### 6.4 阴影质量优化技巧

```python
# 1. 调整阴影相机视锥体以紧密包围场景
sun_lens = sun.get_lens()
sun_lens.set_near_far(1, 200)      # 只覆盖需要的深度范围
sun_lens.set_film_size(100, 100)   # 只覆盖需要的空间范围

# 2. 使用 PSSM（Parallel Split Shadow Maps）
# Panda3D 内置支持通过 CommonFilters
from direct.filter.CommonFilters import CommonFilters
filters = CommonFilters(base.win, base.cam)
# 注意：Panda3D 的 CommonFilters 提供基础后处理，
# 完整 PSSM 需要自定义实现

# 3. 阴影偏移调整（防止 Shadow Acne 和 Peter Panning）
# Shadow Acne：偏移太小，表面自遮挡
# Peter Panning：偏移太大，阴影与物体分离
# 最佳实践：使用法线偏移（Normal Offset Bias）
render.set_shader_input("normal_bias", 0.01)
render.set_shader_input("depth_bias", 0.001)
```

---

## 小结

| 概念 | 核心思想 | Panda3D 实现 |
|------|----------|-------------|
| Phong 光照 | 环境+漫反射+镜面反射 | ShaderGenerator 自动生成 |
| Shadow Map | 从光源视角渲染深度图 | `set_shadow_caster()` |
| PCF 软阴影 | 多次采样取平均 | `sampler2DShadow` + 循环 |
| LightLensNode | 光源兼相机，用于阴影渲染 | 继承 `Light` + `Camera` |
| ShaderGenerator | 根据 RenderState 自动生成 Shader | `set_shader_auto()` |
| LightAttrib | 光照绑定到场景图节点 | `node.set_light(light_np)` |

**核心设计哲学**：
1. **场景图集成**：光源是场景图节点，自动继承变换
2. **自动 Shader**：`set_shader_auto()` 根据实际光照配置生成最优 Shader
3. **双重身份**：`LightLensNode` 同时是光源和相机，优雅地实现阴影渲染
4. **优先级系统**：当光源超过 GPU 限制时，按优先级丢弃低优先级光源