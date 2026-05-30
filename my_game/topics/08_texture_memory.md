# 专题08：纹理与内存管理

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

纹理是 3D 渲染中内存消耗最大的资源。一张 4096×4096 的 RGBA 纹理未压缩时占用 **64MB**，而现代游戏场景可能有数百张这样的纹理。

| 挑战 | 描述 |
|------|------|
| **内存带宽** | GPU 纹理采样需要大量内存带宽，缓存命中率至关重要 |
| **显存限制** | 移动端 GPU 显存可能只有 1-2GB，需要精细管理 |
| **加载延迟** | 从磁盘加载大纹理可能造成卡顿（Stutter） |
| **Mipmap 生成** | 需要预生成多级细节，增加内存占用约 33% |
| **格式多样性** | DXT/BC、ETC、PVRTC 等压缩格式在不同平台支持不同 |
| **纹理池管理** | 避免重复加载同一纹理，需要引用计数和缓存 |

Panda3D 的纹理系统通过 **TexturePool**（全局缓存）、**PreparedGraphicsObjects**（GPU 资源管理）和 **AdaptiveLRU**（自适应淘汰）三层机制解决这些问题。

---

## 2. 数学原理

### 2.1 Mipmap 理论

Mipmap（多级渐远纹理）由 Williams 于 1983 年提出，核心思想是**预计算不同分辨率的纹理版本**，在渲染时根据屏幕像素覆盖面积选择合适的级别。

**Mipmap 级别计算**：

设纹理坐标 (u, v) 在屏幕空间的偏导数为：
```
du/dx, dv/dx（沿 x 方向的变化率）
du/dy, dv/dy（沿 y 方向的变化率）
```

**LOD（Level of Detail）计算**：
```
rho = max(sqrt((du/dx)^2 + (dv/dx)^2), sqrt((du/dy)^2 + (dv/dy)^2))
lambda = log2(rho) + lod_bias
mip_level = clamp(lambda, 0, max_level)
```

**Mipmap 内存占用**：

设基础纹理大小为 W×H，则所有 Mipmap 级别的总内存为：
```
Total = W*H * (1 + 1/4 + 1/16 + ...) = W*H * 4/3 ≈ 1.333 * W*H
```

即 Mipmap 额外增加约 **33%** 的内存占用。

### 2.2 纹理过滤数学

**最近邻过滤**（Nearest）：
```
texel = texture[round(u * W)][round(v * H)]
```

**双线性过滤**（Bilinear）：
```
设 i = floor(u * W), j = floor(v * H)
s = frac(u * W), t = frac(v * H)

texel = (1-s)(1-t)*T[i][j]   + s(1-t)*T[i+1][j]
      + (1-s)t  *T[i][j+1]   + s*t  *T[i+1][j+1]
```

**三线性过滤**（Trilinear = 双线性 + Mipmap 线性插值）：
```
level0 = bilinear_sample(mip[floor(lambda)], u, v)
level1 = bilinear_sample(mip[ceil(lambda)],  u, v)
texel  = lerp(level0, level1, frac(lambda))
```

**各向异性过滤**（Anisotropic）：

沿最大变化方向采样多个点（最多 16 个），解决斜视角下的模糊问题：
```
N = min(anisotropy_degree, max_anisotropy)
沿各向异性方向均匀采样 N 个点，取平均值
```

### 2.3 纹理压缩算法

**DXT1/BC1**（RGB，无 Alpha 或 1 位 Alpha）：
- 将 4×4 像素块压缩为 8 字节（原始 48 字节）
- 压缩比：6:1
- 原理：存储两个端点颜色，其余颜色通过线性插值得到

```
每个 4x4 块：
  color0 (16 bits) + color1 (16 bits) = 2 个端点颜色
  索引表 (32 bits) = 16 个像素各 2 位索引
  总计 8 bytes（原始 48 bytes）
```

**DXT5/BC3**（RGBA）：
- 4×4 块压缩为 16 字节（原始 64 字节）
- 压缩比：4:1
- RGB 部分同 DXT1，Alpha 单独用 8 字节存储

**BC7**（高质量 RGBA）：
- 压缩比 4:1，质量远高于 DXT5
- 支持 7 种模式，根据块内容自适应选择

### 2.4 LRU 缓存淘汰策略

**标准 LRU**（Least Recently Used）：
- 维护一个有序链表，最近使用的在头部
- 淘汰时移除尾部元素
- 时间复杂度：O(1) 访问和淘汰

**Panda3D 的 AdaptiveLRU**：

标准 LRU 的问题：一次性扫描大量纹理会污染缓存（Cache Pollution）。

AdaptiveLRU 的改进：
- 维护**动态列表**（最近使用）和**静态列表**（频繁使用）
- 使用**访问频率权重**：频繁使用的页面即使不是最近使用也不会被淘汰
- 每帧调用 `begin_epoch()` 更新统计信息

```
score = alpha * recency + (1 - alpha) * frequency
淘汰 score 最低的页面
```

---

## 3. 工程实践

### 3.1 纹理生命周期

```
磁盘文件
  ↓ TexturePool::load_texture()
系统内存（RAM Image）
  ↓ Texture::prepare() / 首次渲染时自动触发
GPU 显存（TextureContext）
  ↓ 渲染完成后（可选）
释放 RAM Image（节省系统内存）
```

**关键设计**：Panda3D 默认在纹理上传 GPU 后**自动释放 RAM Image**，节省系统内存。可通过 `keep-texture-ram true` 配置保留。

### 3.2 TexturePool 缓存机制

TexturePool 是一个**全局单例**，维护文件名到 Texture 对象的映射：

```
TexturePool._textures: dict[filename -> WeakRef<Texture>]
```

**引用计数**：Texture 继承自 `TypedWritableReferenceCount`，当引用计数归零时自动释放。

**缓存查找流程**：
```
load_texture(filename)
  ├── 检查 _textures[filename] 是否存在且有效
  │   ├── 存在 → 直接返回（命中缓存）
  │   └── 不存在 → 从磁盘加载
  │       ├── 读取图像文件到 RAM
  │       ├── 创建 Texture 对象
  │       ├── 存入 _textures[filename]
  │       └── 返回 Texture
```

### 3.3 GPU 资源管理（PreparedGraphicsObjects）

每个 GraphicsStateGuardian 关联一个 `PreparedGraphicsObjects`，管理该 GSG 上的所有 GPU 资源：

```
PreparedGraphicsObjects
  ├── _prepared_textures: set<TextureContext*>
  ├── _released_textures: set<TextureContext*>（待释放队列）
  ├── _enqueued_textures: set<Texture*>（待上传队列）
  └── _graphics_memory_lru: AdaptiveLru（显存 LRU）
```

**纹理上传流程**：
```
Texture::prepare(gsg)
  → PreparedGraphicsObjects::enqueue_texture(tex)
  → 在渲染线程中：GSG::prepare_texture(tex)
  → 创建 TextureContext（包含 OpenGL texture ID）
  → 上传像素数据到 GPU
  → 可选：释放 RAM Image
```

### 3.4 显存限制与 LRU 淘汰

当显存超过限制时，AdaptiveLRU 自动淘汰最少使用的纹理：

```python
# 设置显存限制（字节）
base.win.get_gsg().get_prepared_objects().set_graphics_memory_limit(512 * 1024 * 1024)  # 512MB
```

淘汰流程：
```
AdaptiveLru::consider_evict()
  ├── 计算当前总大小
  ├── 若超过 max_size：
  │   ├── 从静态列表尾部选择淘汰候选
  │   └── 调用 TextureContext::evict_lru()
  │       → PreparedGraphicsObjects::release_texture(ctx)
  │       → 删除 OpenGL 纹理对象
  │       → 下次使用时重新上传
```

---

## 4. Panda3D 源码剖析

### 4.1 Texture 类结构

**文件**：[`texture.h`](panda/src/gobj/texture.h)

```cpp
// texture.h:73
class EXPCL_PANDA_GOBJ Texture
    : public TypedWritableReferenceCount, public Namable {
public:
  // 纹理类型
  enum TextureType {
    TT_1d_texture,
    TT_2d_texture,       // 最常用
    TT_3d_texture,
    TT_2d_texture_array,
    TT_cube_map,         // 环境贴图
    TT_buffer_texture,   // 用于 GPGPU
    TT_cube_map_array,
    TT_1d_texture_array,
  };

  // 像素格式（部分）
  enum Format {
    F_rgb,    // 任意 RGB
    F_rgba,   // 任意 RGBA
    F_rgba8,  // 8 bits per channel
    F_rgba16, // 16 bits per channel（HDR）
    F_rgba32, // 32 bits per channel（float）
    F_srgb,   // sRGB 色彩空间
    F_srgb_alpha,
    F_depth_component,   // 深度纹理
    F_r11_g11_b10,       // 压缩浮点（HDR 效率高）
    // ... 共 50+ 种格式
  };

  // 压缩模式
  enum CompressionMode {
    CM_default,  // 根据配置决定
    CM_off,      // 不压缩
    CM_on,       // 驱动选择最佳压缩
    CM_dxt1,     // BC1: RGB，压缩比 6:1
    CM_dxt5,     // BC3: RGBA，压缩比 4:1
    CM_rgtc,     // BC4/BC5: 法线贴图专用
    CM_etc2,     // OpenGL ES 3.0 标准
    // ...
  };

  // 质量级别
  enum QualityLevel {
    QL_fastest,  // 最低质量，最快速度
    QL_normal,   // 平衡
    QL_best,     // 最高质量
  };
};
```

**Texture 的双缓冲数据**（PipelineCycler）：

```cpp
// texture.h 内部 CData 结构（简化）
class CData : public CycleData {
  int _x_size, _y_size, _z_size;  // 纹理尺寸
  int _num_components;             // 通道数
  Format _format;
  CompressionMode _compression;
  PTA_uchar _ram_image;            // 系统内存中的像素数据
  int _ram_image_size;
  UpdateSeq _image_modified;       // 用于检测纹理是否被修改
};
```

### 4.2 SamplerState 采样器状态

**文件**：[`samplerState.h`](panda/src/gobj/samplerState.h)

```cpp
// samplerState.h:35
class EXPCL_PANDA_GOBJ SamplerState : public MemoryBase {
public:
  enum FilterType {
    FT_nearest,                // 最近邻（像素风格）
    FT_linear,                 // 双线性（平滑）
    FT_nearest_mipmap_nearest, // Mipmap + 最近邻
    FT_linear_mipmap_nearest,  // Mipmap + 双线性
    FT_nearest_mipmap_linear,  // Mipmap 线性混合 + 最近邻
    FT_linear_mipmap_linear,   // 三线性（最高质量）
    FT_shadow,                 // 阴影贴图比较采样
  };

  enum WrapMode {
    WM_clamp,        // 超出范围钳制到边缘
    WM_repeat,       // 重复平铺
    WM_mirror,       // 镜像重复
    WM_mirror_once,  // 镜像一次后钳制
    WM_border_color, // 超出范围使用边框颜色
  };

  // 各向异性过滤度数（1=关闭，2-16=开启）
  void set_anisotropic_degree(int anisotropic_degree);

  // LOD 偏移（正值=更模糊，负值=更清晰）
  void set_lod_bias(PN_stdfloat lod_bias);

  // LOD 范围限制
  void set_min_lod(PN_stdfloat min_lod);
  void set_max_lod(PN_stdfloat max_lod);
};
```

### 4.3 TexturePool 全局缓存

**文件**：[`texturePool.h`](panda/src/gobj/texturePool.h)

```cpp
// texturePool.h:37
class EXPCL_PANDA_GOBJ TexturePool {
public:
  // 检查纹理是否已缓存
  static bool has_texture(const Filename &filename);

  // 获取已缓存的纹理（不加载）
  static Texture *get_texture(const Filename &filename,
                               int primary_file_num_channels = 0,
                               bool read_mipmaps = false);

  // 加载纹理（缓存未命中时从磁盘读取）
  static Texture *load_texture(const Filename &filename,
                                int primary_file_num_channels = 0,
                                bool read_mipmaps = false,
                                const LoaderOptions &options = LoaderOptions(),
                                const SamplerState &sampler = SamplerState());

  // 特殊纹理加载
  static Texture *load_3d_texture(const Filename &filename_pattern, ...);
  static Texture *load_cube_map(const Filename &filename_pattern, ...);

  // 手动管理
  static void add_texture(Texture *texture);
  static void release_texture(Texture *texture);
  static void release_all_textures();

  // 垃圾回收（清理引用计数为0的纹理）
  static int garbage_collect();

private:
  // 内部：文件名 -> Texture 的映射
  typedef pmap<Filename, PT(Texture)> Textures;
  Textures _textures;
  Mutex _lock;
};
```

### 4.4 PreparedGraphicsObjects 显存管理

**文件**：[`preparedGraphicsObjects.h`](panda/src/gobj/preparedGraphicsObjects.h)

```cpp
// preparedGraphicsObjects.h:62
class EXPCL_PANDA_GOBJ PreparedGraphicsObjects : public ReferenceCount {
public:
  // 显存限制
  void set_graphics_memory_limit(size_t limit);
  size_t get_graphics_memory_limit() const;

  // 纹理管理
  void enqueue_texture(Texture *tex);          // 加入上传队列
  bool is_texture_queued(const Texture *tex) const;
  bool dequeue_texture(Texture *tex);          // 取消上传
  bool is_texture_prepared(const Texture *tex) const;
  TextureContext *prepare_texture(Texture *tex, int view);  // 立即上传
  void release_texture(TextureContext *tc);    // 释放 GPU 资源

  // 其他资源（Geom、Shader、Buffer 等）
  void enqueue_geom(Geom *geom);
  ShaderContext *prepare_shader(Shader *shader);
  VertexBufferContext *prepare_vertex_buffer(GeomVertexArrayData *data);

  // 统计
  int get_num_queued() const;
  int get_num_prepared() const;
  void show_graphics_memory_lru(std::ostream &out) const;

private:
  // AdaptiveLRU 管理显存使用
  AdaptiveLru _graphics_memory_lru;

  // 各类资源的集合
  typedef pset<TextureContext *> PreparedTextures;
  PreparedTextures _prepared_textures;

  typedef pset<Texture *> EnqueuedTextures;
  EnqueuedTextures _enqueued_textures;
};
```

### 4.5 AdaptiveLRU 自适应淘汰

**文件**：[`adaptiveLru.h`](panda/src/gobj/adaptiveLru.h)

```cpp
// adaptiveLru.h:45
class EXPCL_PANDA_GOBJ AdaptiveLru : public Namable {
public:
  explicit AdaptiveLru(std::string name, size_t max_size);

  size_t get_total_size() const;
  size_t get_max_size() const;
  void set_max_size(size_t max_size);

  // 检查是否需要淘汰，若需要则执行
  void consider_evict();

  // 强制淘汰到目标大小
  void evict_to(size_t target_size);

  // 每帧调用，更新访问频率统计
  void begin_epoch();

  // 权重：控制频率 vs 时间的平衡
  void set_weight(PN_stdfloat weight);  // 0=纯LRU, 1=纯频率

  // 每帧最多更新的页面数（避免性能峰值）
  void set_max_updates_per_frame(int max_updates_per_frame);

private:
  enum LruPagePriority {
    LPP_Highest = 0,
    LPP_High    = 10,
    LPP_New     = 20,
    LPP_Normal  = 25,
    LPP_Low     = 35,
    LPP_Lowest  = 50,
  };

  // 动态列表（最近使用）和静态列表（频繁使用）
  AdaptiveLruPageDynamicList _dynamic_list;
  AdaptiveLruPageStaticList  _static_list;
};
```
## 5. 代码演示

### 5.1 Python：基本纹理加载与设置

```python
from panda3d.core import (
    Texture, TextureStage, SamplerState,
    LoaderOptions, Filename
)

# 基本加载（通过 TexturePool 缓存）
tex = loader.load_texture('textures/diffuse.png')

# 设置采样参数
tex.set_minfilter(SamplerState.FT_linear_mipmap_linear)  # 三线性过滤
tex.set_magfilter(SamplerState.FT_linear)                # 双线性放大
tex.set_wrap_u(SamplerState.WM_repeat)                   # U 方向重复
tex.set_wrap_v(SamplerState.WM_repeat)                   # V 方向重复
tex.set_anisotropic_degree(8)                            # 8x 各向异性

# 应用到节点
model.set_texture(tex)

# 使用 TextureStage 多重纹理
ts_diffuse = TextureStage('diffuse')
ts_normal  = TextureStage('normal')
ts_normal.set_mode(TextureStage.M_normal)  # 法线贴图模式

model.set_texture(ts_diffuse, diffuse_tex, 1)
model.set_texture(ts_normal,  normal_tex,  2)
```

### 5.2 Python：纹理格式与压缩

```python
from panda3d.core import Texture, LoaderOptions

# 加载时指定压缩
options = LoaderOptions()
options.set_texture_flags(LoaderOptions.TF_preload)  # 立即加载到 RAM

# 启用自动压缩（驱动选择最佳格式）
tex = loader.load_texture('textures/diffuse.png')
tex.set_compression(Texture.CM_on)  # 自动压缩

# 指定具体压缩格式
tex.set_compression(Texture.CM_dxt5)  # BC3: RGBA 压缩

# 法线贴图使用 RGTC（BC5）
normal_tex = loader.load_texture('textures/normal.png')
normal_tex.set_compression(Texture.CM_rgtc)  # 专为法线贴图优化

# 检查压缩是否被支持
gsg = base.win.get_gsg()
if gsg.get_supports_compressed_texture_format(Texture.CM_dxt5):
    tex.set_compression(Texture.CM_dxt5)
else:
    tex.set_compression(Texture.CM_off)

# 查看纹理内存占用
print(f"纹理大小：{tex.get_x_size()}x{tex.get_y_size()}")
print(f"格式：{tex.get_format()}")
print(f"RAM 占用：{tex.get_ram_image_size()} bytes")
```

### 5.3 Python：Mipmap 控制

```python
from panda3d.core import Texture, SamplerState

# 加载时自动生成 Mipmap
tex = loader.load_texture('textures/diffuse.png')
tex.generate_mipmaps()  # 在 CPU 上生成 Mipmap

# 或者从文件加载预生成的 Mipmap（DDS 格式）
tex = loader.load_texture('textures/diffuse.dds', read_mipmaps=True)

# 禁用 Mipmap（UI 元素、字体等）
tex.set_minfilter(SamplerState.FT_linear)  # 不使用 Mipmap

# LOD 偏移（负值=更清晰，正值=更模糊）
tex.set_lod_bias(-0.5)  # 稍微更清晰

# 限制 Mipmap 范围
tex.set_min_lod(0)    # 最高分辨率级别
tex.set_max_lod(4)    # 最多使用到第4级（1/16 分辨率）
```

### 5.4 Python：纹理池管理

```python
from panda3d.core import TexturePool, Texture

# 检查纹理是否已缓存
filename = 'textures/diffuse.png'
if TexturePool.has_texture(filename):
    tex = TexturePool.get_texture(filename)
    print("从缓存获取纹理")
else:
    tex = TexturePool.load_texture(filename)
    print("从磁盘加载纹理")

# 手动添加程序化纹理到池
proc_tex = Texture('procedural_noise')
proc_tex.setup_2d_texture(256, 256, Texture.T_unsigned_byte, Texture.F_rgba)
# ... 填充像素数据 ...
TexturePool.add_texture(proc_tex)

# 释放特定纹理（减少引用计数）
TexturePool.release_texture(tex)

# 垃圾回收（清理引用计数为0的纹理）
released = TexturePool.garbage_collect()
print(f"释放了 {released} 个纹理")

# 释放所有纹理（场景切换时）
TexturePool.release_all_textures()
```

### 5.5 Python：显存管理与 LRU

```python
from panda3d.core import Texture

# 获取 PreparedGraphicsObjects
pgo = base.win.get_gsg().get_prepared_objects()

# 设置显存限制（512MB）
pgo.set_graphics_memory_limit(512 * 1024 * 1024)

# 查看当前显存使用情况
print(f"已准备纹理数：{pgo.get_num_prepared()}")
print(f"待上传纹理数：{pgo.get_num_queued()}")

# 显示 LRU 状态（调试用）
import sys
pgo.show_graphics_memory_lru(sys.stdout)
pgo.show_residency_trackers(sys.stdout)

# 手动预加载纹理到 GPU（避免首帧卡顿）
def preload_textures(texture_list):
    gsg = base.win.get_gsg()
    for tex in texture_list:
        tex.prepare(gsg.get_prepared_objects())
    # 强制立即上传（在渲染线程中）
    base.graphicsEngine.render_frame()

# 释放特定纹理的 GPU 资源
def release_gpu_texture(tex):
    gsg = base.win.get_gsg()
    pgo = gsg.get_prepared_objects()
    # 纹理会在下次使用时重新上传
    pgo.release_all()  # 释放所有（场景切换时）
```

### 5.6 Python：程序化纹理生成

```python
from panda3d.core import Texture, PNMImage
import math

def create_checkerboard_texture(size=256, tile=8):
    """创建棋盘格纹理"""
    img = PNMImage(size, size)
    tile_size = size // tile
    for y in range(size):
        for x in range(size):
            if (x // tile_size + y // tile_size) % 2 == 0:
                img.set_pixel(x, y, 1, 1, 1)  # 白色
            else:
                img.set_pixel(x, y, 0, 0, 0)  # 黑色

    tex = Texture('checkerboard')
    tex.load(img)
    tex.generate_mipmaps()
    return tex

def create_gradient_texture(width=256, height=1):
    """创建渐变纹理（用于颜色映射）"""
    tex = Texture('gradient')
    tex.setup_2d_texture(width, height,
                         Texture.T_unsigned_byte,
                         Texture.F_rgba)
    # 直接写入像素数据
    data = bytearray(width * height * 4)
    for x in range(width):
        t = x / (width - 1)
        r = int(t * 255)
        g = int((1 - t) * 255)
        b = 128
        a = 255
        idx = x * 4
        data[idx:idx+4] = [r, g, b, a]
    tex.set_ram_image(bytes(data))
    return tex

def create_noise_texture(size=256):
    """创建噪声纹理"""
    import random
    tex = Texture('noise')
    tex.setup_2d_texture(size, size,
                         Texture.T_unsigned_byte,
                         Texture.F_luminance)
    data = bytearray(size * size)
    for i in range(size * size):
        data[i] = random.randint(0, 255)
    tex.set_ram_image(bytes(data))
    tex.generate_mipmaps()
    return tex
```

### 5.7 GLSL：Shader 中的纹理采样

```glsl
// 顶点着色器
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
// 片段着色器
#version 330

uniform sampler2D p3d_Texture0;   // 漫反射贴图
uniform sampler2D p3d_Texture1;   // 法线贴图
uniform sampler2D p3d_Texture2;   // 高光贴图

in vec2 texcoord;
out vec4 fragColor;

void main() {
    // 基础纹理采样
    vec4 diffuse = texture(p3d_Texture0, texcoord);

    // 法线贴图解码（从 [0,1] 映射到 [-1,1]）
    vec3 normal = texture(p3d_Texture1, texcoord).rgb * 2.0 - 1.0;
    normal = normalize(normal);

    // 高光强度
    float specular = texture(p3d_Texture2, texcoord).r;

    // 简单光照
    vec3 light_dir = normalize(vec3(1, 1, 1));
    float ndotl = max(dot(normal, light_dir), 0.0);

    fragColor = vec4(diffuse.rgb * ndotl, diffuse.a);
}
```

```python
# Python 端设置多重纹理 Shader
from panda3d.core import Shader, TextureStage

shader = Shader.load(Shader.SL_GLSL,
    vertex='shaders/pbr.vert',
    fragment='shaders/pbr.frag')
model.set_shader(shader)

# 绑定纹理到 Shader 槽位
model.set_shader_input('p3d_Texture0', diffuse_tex)
model.set_shader_input('p3d_Texture1', normal_tex)
model.set_shader_input('p3d_Texture2', specular_tex)
```

---

## 6. 性能优化

### 6.1 纹理格式选择

| 用途 | 推荐格式 | 压缩 | 内存（1024x1024） |
|------|---------|------|-----------------|
| 漫反射（不透明） | F_rgb / F_srgb | DXT1/BC1 | 0.5MB |
| 漫反射（透明） | F_rgba / F_srgb_alpha | DXT5/BC3 | 1MB |
| 法线贴图 | F_rg | RGTC/BC5 | 1MB |
| 高光/粗糙度 | F_luminance | BC4 | 0.5MB |
| HDR 环境贴图 | F_rgba16 | 无 | 8MB |
| UI 元素 | F_rgba | 无（或 DXT5） | 4MB |
| 深度纹理 | F_depth_component24 | 无 | 4MB |

### 6.2 Mipmap 策略

```python
# 需要 Mipmap 的情况（3D 场景中的物体）
tex.set_minfilter(SamplerState.FT_linear_mipmap_linear)  # 三线性
tex.generate_mipmaps()

# 不需要 Mipmap 的情况（UI、全屏后处理）
ui_tex.set_minfilter(SamplerState.FT_linear)  # 节省 33% 内存

# 预生成 Mipmap（离线工具，质量更好）
# 使用 textures/diffuse.dds（包含预生成 Mipmap）
tex = loader.load_texture('textures/diffuse.dds', read_mipmaps=True)
```

### 6.3 纹理图集（Texture Atlas）

```python
# 将多个小纹理合并为一张大纹理，减少 Draw Call
# 使用 UV 偏移访问不同区域

# 假设 atlas 是 4x4 的图集（每格 256x256）
atlas_tex = loader.load_texture('textures/atlas.png')

# 在 Shader 中使用 UV 偏移
model.set_shader_input('uv_offset', (0.25, 0.0))   # 第2列第1行
model.set_shader_input('uv_scale',  (0.25, 0.25))  # 每格占 1/4
```

### 6.4 异步纹理加载

```python
from panda3d.core import AsyncTaskManager, Loader, LoaderOptions

# 异步加载（不阻塞主线程）
def on_texture_loaded(tex):
    if tex:
        model.set_texture(tex)
        print(f"纹理加载完成：{tex.get_name()}")
    else:
        print("纹理加载失败")

# 使用 Panda3D 的异步加载器
request = loader.load_texture(
    'textures/large_texture.png',
    callback=on_texture_loaded
)

# 取消加载（如果不再需要）
# request.cancel()
```

### 6.5 内存优化技巧

```python
# 1. 上传 GPU 后释放 RAM Image（默认行为）
# 在 config.prc 中：
# keep-texture-ram false  （默认）

# 2. 强制保留 RAM Image（需要 CPU 端读取时）
tex.set_keep_ram_image(True)

# 3. 使用较小的纹理尺寸（移动端）
# 在 config.prc 中：
# texture-scale 0.5  # 所有纹理缩小到 50%

# 4. 限制最大纹理尺寸
# texture-scale-limit 1024  # 最大 1024x1024

# 5. 场景切换时清理
def on_scene_unload():
    TexturePool.release_all_textures()
    TexturePool.garbage_collect()
    # 强制 GPU 释放
    base.win.get_gsg().get_prepared_objects().release_all()
```

### 6.6 性能监控

```python
# 监控纹理内存使用
def print_texture_stats():
    pgo = base.win.get_gsg().get_prepared_objects()
    print(f"GPU 纹理数量：{pgo.get_num_prepared()}")
    print(f"显存限制：{pgo.get_graphics_memory_limit() / 1024 / 1024:.1f} MB")

    # 列出所有已加载纹理
    textures = TexturePool.find_all_textures()
    total_ram = sum(t.get_ram_image_size() for t in textures
                    if t.has_ram_image())
    print(f"RAM 中纹理数：{len(textures)}")
    print(f"RAM 纹理总大小：{total_ram / 1024 / 1024:.1f} MB")

# 每 5 秒打印一次
taskMgr.do_method_later(5.0, lambda t: (print_texture_stats(), t.cont)[1],
                         'texture_stats')
```

---

## 小结

| 知识点 | 核心要点 |
|--------|---------|
| **Mipmap** | 预计算多级分辨率；额外占用 33% 内存；三线性过滤需要 Mipmap |
| **纹理过滤** | 最近邻=像素风格；双线性=平滑；三线性=最高质量；各向异性=斜视角 |
| **纹理压缩** | DXT1=RGB 6:1；DXT5=RGBA 4:1；RGTC=法线贴图；ETC2=移动端 |
| **TexturePool** | 全局缓存，相同文件名只加载一次；引用计数自动管理生命周期 |
| **PreparedGraphicsObjects** | 管理 GPU 资源；enqueue=异步上传；release=释放显存 |
| **AdaptiveLRU** | 自适应淘汰；兼顾时间局部性和频率；防止缓存污染 |
| **RAM Image** | 上传 GPU 后默认释放；keep-texture-ram 可保留 |
| **sRGB** | 漫反射贴图用 F_srgb；法线/高光贴图用线性格式 |

**Panda3D 纹理系统的设计哲学**：
- 透明缓存：TexturePool 对用户透明，自动避免重复加载
- 延迟上传：首次渲染时才上传 GPU，避免启动时卡顿
- 自动释放：上传后释放 RAM Image，最小化内存占用
- 可配置：通过 config.prc 全局控制纹理质量和内存策略
