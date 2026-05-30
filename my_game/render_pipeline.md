# Panda3D 渲染管线深度解析

> 基于源码版本：panda3d-master  
> 核心目录：`panda/src/display/`、`panda/src/pgraph/`、`panda/src/cull/`、`panda/src/glstuff/`

---

## 目录

1. [总体架构概览](#1-总体架构概览)
2. [核心类关系图](#2-核心类关系图)
3. [阶段一：App 阶段 — render_frame() 入口](#3-阶段一app-阶段--render_frame-入口)
4. [阶段二：场景准备 — setup_scene()](#4-阶段二场景准备--setup_scene)
5. [阶段三：Cull 阶段 — 场景图遍历与视锥剔除](#5-阶段三cull-阶段--场景图遍历与视锥剔除)
6. [阶段四：Bin 分类与排序 — CullResult](#6-阶段四bin-分类与排序--cullresult)
7. [阶段五：Draw 阶段 — 提交 GPU 绘制命令](#7-阶段五draw-阶段--提交-gpu-绘制命令)
8. [阶段六：状态管理 — RenderState & GSG](#8-阶段六状态管理--renderstate--gsg)
9. [阶段七：Shader 管线](#9-阶段七shader-管线)
10. [阶段八：帧缓冲翻转 — Flip](#10-阶段八帧缓冲翻转--flip)
11. [多线程模型](#11-多线程模型)
12. [完整调用链汇总](#12-完整调用链汇总)

---

## 1. 总体架构概览

Panda3D 的渲染管线是一个**三阶段流水线**：

```
App 线程                Cull 线程              Draw 线程
─────────────────────  ─────────────────────  ─────────────────────
render_frame()         CullTraverser::         CullResult::draw()
  └─ setup_scene()       traverse()              └─ CullBin::draw()
  └─ open_windows()      └─ do_traverse()          └─ CullableObject::draw()
  └─ pipeline->cycle()   └─ add_for_draw()           └─ GSG::begin_draw_primitives()
                         └─ BinCullHandler::           └─ GSG::draw_triangles()
                             record_object()              └─ glDrawRangeElements()
```

**关键设计原则：**
- **Cull 与 Draw 分离**：Cull 阶段遍历场景图，收集可见几何体；Draw 阶段将收集结果提交 GPU
- **状态守卫（State Guardian）**：GSG 追踪当前 GPU 状态，避免冗余状态切换
- **Bin 排序**：几何体按 Bin 分类（不透明/透明/固定顺序），保证正确的渲染顺序
- **Pipeline Cycler**：多线程下通过 Pipeline 对象在帧间安全传递数据

---

## 2. 核心类关系图

```
GraphicsEngine                          ← 渲染总控制器（单例）
  ├─ GraphicsOutput (Window/Buffer)     ← 渲染目标（窗口或离屏缓冲）
  │    ├─ GraphicsStateGuardian (GSG)   ← GPU 状态守卫，封装图形 API
  │    └─ DisplayRegion[]               ← 窗口内的矩形渲染区域
  │         ├─ Camera → NodePath        ← 摄像机节点路径
  │         ├─ CullTraverser            ← 场景图遍历器
  │         └─ CullResult               ← Cull 结果（按 Bin 组织）
  │
  ├─ WindowRenderer (_app)              ← App 线程渲染器
  └─ RenderThread[]                     ← Cull/Draw 辅助线程

SceneSetup                              ← 单帧场景参数快照
  ├─ scene_root (NodePath)
  ├─ camera_transform (TransformState)
  ├─ world_transform (TransformState)
  ├─ view_frustum (GeometricBoundingVolume)
  └─ lens (Lens)

RenderState                             ← 不可变渲染状态集合（引用计数+缓存）
  └─ RenderAttrib[]                     ← 各类属性（Shader/Texture/Depth/Blend…）

CullResult                              ← 一帧的 Cull 输出
  └─ CullBin[]                          ← 按 bin_index 组织的几何体桶
       └─ CullableObject[]              ← 单个可绘制对象（Geom + State + Transform）
```

---

## 3. 阶段一：App 阶段 — `render_frame()` 入口

**源码位置：** [`graphicsEngine.cxx:713`](panda/src/display/graphicsEngine.cxx:713)

```cpp
void GraphicsEngine::render_frame() {
    // 1. 确保所有窗口已打开（懒初始化）
    open_windows();

    // 2. 处理线程模型变更
    if (_threading_model_changed) {
        do_reassign_windows(current_thread);
    }

    // 3. 预计算场景包围盒（App 线程提前算，减少 Cull 线程重算）
    for each window:
        for each DisplayRegion:
            scene.get_bounds(current_thread);  // 触发包围盒更新

    // 4. 释放上一帧已上传纹理的 RAM 副本
    for each loaded_texture:
        tex->texture_uploaded();

    // 5. App 线程执行自己的 Cull+Draw（单线程模型）
    _app.do_frame(this, current_thread);

    // 6. 等待所有辅助线程完成上一帧
    for each render_thread:
        wait for TS_wait state;

    // 7. 刷新各类缓存
    GeomCacheManager::flush_level();
    RenderState::flush_level();
    TransformState::flush_level();

    // 8. 推进 Pipeline（多线程模型下的帧间数据同步）
    _pipeline->cycle();

    // 9. 推进时钟
    _clock->tick(current_thread);

    // 10. 通知所有辅助线程开始新帧
    for each render_thread:
        thread->_thread_state = TS_do_frame;
        thread->_cv_start.notify();
}
```

**关键点：**
- [`_app.do_frame()`](panda/src/display/graphicsEngine.cxx:2679) 在单线程模式下同时执行 Cull 和 Draw
- [`_pipeline->cycle()`](panda/src/display/graphicsEngine.cxx:852) 是多线程安全的帧间数据切换点
- `_flip_state` 状态机控制翻转时机：`FS_draw → FS_sync → FS_flip`

---

## 4. 阶段二：场景准备 — `setup_scene()`

**源码位置：** [`graphicsEngine.cxx:1909`](panda/src/display/graphicsEngine.cxx:1909)

```cpp
PT(SceneSetup) GraphicsEngine::setup_scene(GraphicsStateGuardian *gsg,
                                            DisplayRegionPipelineReader *dr) {
    // 1. 获取摄像机节点
    NodePath camera = dr->get_camera();
    Camera *camera_node = DCAST(Camera, camera.node());

    // 2. 获取镜头
    Lens *lens = camera_node->get_lens(lens_index);

    // 3. 确定场景根节点
    NodePath scene_root = camera_node->get_scene();
    if (scene_root.is_empty())
        scene_root = camera.get_top();  // 默认：摄像机所在场景树的根

    // 4. 计算变换矩阵
    CPT(TransformState) camera_transform = camera.get_transform(scene_parent);
    CPT(TransformState) world_transform  = scene_parent.get_transform(camera);

    // 5. 填充 SceneSetup 快照
    scene_setup->set_scene_root(scene_root);
    scene_setup->set_camera_transform(camera_transform);
    scene_setup->set_world_transform(world_transform);
    scene_setup->set_lens(lens);
    scene_setup->set_initial_state(camera_node->get_initial_state());

    // 6. 坐标系变换（处理 Y-up / Z-up 差异）
    CPT(TransformState) cs_transform = gsg->get_cs_transform_for(lens->get_coordinate_system());
    scene_setup->set_cs_world_transform(cs_transform->compose(world_transform));

    // 7. 构建视锥体（用于 Cull 阶段的视锥剔除）
    if (view_frustum_cull) {
        PT(BoundingVolume) bv = scene_setup->get_cull_bounds();
        local_frustum->xform(cull_center_transform->get_mat());
        scene_setup->set_view_frustum(local_frustum);
    }

    return scene_setup;
}
```

**`SceneSetup` 包含的关键数据：**

| 字段 | 类型 | 含义 |
|------|------|------|
| `scene_root` | `NodePath` | 场景树根节点 |
| `camera_path` | `NodePath` | 摄像机节点路径 |
| `camera_transform` | `TransformState*` | 场景→摄像机变换 |
| `world_transform` | `TransformState*` | 摄像机→场景变换（View Matrix） |
| `cs_world_transform` | `TransformState*` | 含坐标系修正的 View Matrix |
| `view_frustum` | `GeometricBoundingVolume*` | 视锥体（用于剔除） |
| `lens` | `Lens*` | 投影参数 |
| `initial_state` | `RenderState*` | 摄像机初始渲染状态 |

---

## 5. 阶段三：Cull 阶段 — 场景图遍历与视锥剔除

### 5.1 入口：`do_cull()`

**源码位置：** [`graphicsEngine.cxx:1261`](panda/src/display/graphicsEngine.cxx:1261)

```cpp
void GraphicsEngine::do_cull(CullHandler *cull_handler,
                              SceneSetup *scene_setup,
                              GraphicsStateGuardian *gsg,
                              Thread *current_thread) {
    // 从 DisplayRegion 获取（或创建）CullTraverser
    CullTraverser *trav = dr->get_cull_traverser();

    // 绑定 CullHandler（决定几何体去哪里：Bin 或直接 Draw）
    trav->set_cull_handler(cull_handler);

    // 设置场景参数（摄像机、视锥体、初始状态等）
    trav->set_scene(scene_setup, gsg, dr->get_incomplete_render());

    // 从场景根节点开始遍历
    trav->traverse(scene_setup->get_scene_root());
    trav->end_traverse();
}
```

### 5.2 `CullTraverser::set_scene()` — 初始化遍历参数

**源码位置：** [`cullTraverser.cxx:88`](panda/src/pgraph/cullTraverser.cxx:88)

```cpp
void CullTraverser::set_scene(SceneSetup *scene_setup,
                               GraphicsStateGuardianBase *gsg,
                               bool dr_incomplete_render) {
    _scene_setup   = scene_setup;
    _gsg           = gsg;
    _initial_state = scene_setup->get_initial_state();  // 摄像机初始状态
    _camera_mask   = camera->get_camera_mask();          // 摄像机可见掩码
    _view_frustum  = scene_setup->get_view_frustum();   // 视锥体
    _tag_state_key = camera->get_tag_state_key();       // Tag 状态键
}
```

### 5.3 `CullTraverser::traverse()` — 开始遍历

**源码位置：** [`cullTraverser.cxx:115`](panda/src/pgraph/cullTraverser.cxx:115)

```cpp
void CullTraverser::traverse(const NodePath &root) {
    // 构建初始遍历数据（根节点，单位变换，初始状态，视锥体）
    CullTraverserData data(root,
                           TransformState::make_identity(),
                           _initial_state,
                           _view_frustum,
                           _current_thread);

    // 检查根节点是否在视锥体内
    if (data.is_in_view(_camera_mask)) {
        do_traverse(data);
    }
}
```

### 5.4 `CullTraverser::do_traverse()` — 核心递归遍历

**源码位置：** [`cullTraverser.cxx:178`](panda/src/pgraph/cullTraverser.cxx:178)

```cpp
void CullTraverser::do_traverse(CullTraverserData &data) {
    PandaNode *node = data.node();
    int fancy_bits = node_reader->get_fancy_bits();

    // 1. 处理特殊节点属性（包围盒显示、Cull 回调等）
    if (fancy_bits & ~PandaNode::FB_renderable) {
        data.apply_transform_and_state(this);  // 累积变换和状态

        if (fancy_bits & PandaNode::FB_cull_callback) {
            if (!node->cull_callback(this, data)) return;  // 自定义剔除
        }
    }

    // 2. 如果节点可渲染，提交给 CullHandler
    if ((fancy_bits & PandaNode::FB_renderable) &&
        !data.is_this_node_hidden(_camera_mask)) {
        node->add_for_draw(this, data);  // GeomNode 在此提交几何体
    }

    // 3. 递归遍历所有子节点
    PandaNode::Children children = node_reader->get_children();
    for (int i = 0; i < num_children; ++i) {
        traverse_down(data, child, data._state);
    }
}
```

### 5.5 视锥剔除机制

**`CullTraverserData::is_in_view()`** 在每个节点处检查：

```
节点包围盒 ∩ 视锥体 = ?
  ├─ 完全在外 → 跳过整个子树（剔除）
  ├─ 完全在内 → 子树无需再检查（优化）
  └─ 部分相交 → 继续向下检查子节点
```

**`CullTraverserData` 携带的遍历状态：**

| 字段 | 含义 |
|------|------|
| `_net_transform` | 当前节点的世界变换（累积） |
| `_state` | 当前节点的渲染状态（累积 compose） |
| `_view_frustum` | 当前有效视锥体（可被 ClipPlane 裁剪） |
| `_cull_planes` | 额外裁剪平面 |
| `_draw_mask` | 可见性掩码 |
| `_instances` | 实例化渲染的实例列表 |

---

## 6. 阶段四：Bin 分类与排序 — `CullResult`

### 6.1 两种 CullHandler

**单线程（cull+draw together）：**

```cpp
// drawCullHandler.cxx:28
void DrawCullHandler::record_object(CullableObject &&object,
                                    const CullTraverser *traverser) {
    // 立即 munge（顶点格式转换）并绘制，无需 Bin
    object.munge_geom(_gsg, _gsg->get_geom_munger(object._state, ...), ...);
    draw(&object, _gsg, force, current_thread);
}
```

**多线程（cull to bins）：**

```cpp
// binCullHandler.cxx:22
void BinCullHandler::record_object(CullableObject &&object,
                                   const CullTraverser *traverser) {
    // 将对象放入 CullResult 的对应 Bin
    _cull_result->add_object(std::move(object), traverser);
}
```

### 6.2 `CullResult::add_object()` — Bin 分配逻辑

**源码位置：** [`cullResult.cxx:107`](panda/src/pgraph/cullResult.cxx:107)

```cpp
void CullResult::add_object(CullableObject &&object,
                             const CullTraverser *traverser) {
    // 1. 处理法线缩放（auto rescale）
    if (rescale->get_mode() == RescaleNormalAttrib::M_auto) {
        // 根据变换是否均匀缩放，选择 M_none / M_rescale / M_normalize
    }

    // 2. 处理透明度模式
    switch (trans->get_mode()) {
    case M_alpha:           // 标准 alpha 混合
    case M_binary:          // 二值 alpha 测试
    case M_multisample:     // 多重采样
    case M_dual:            // 双通道：不透明部分→opaque bin，透明部分→transparent bin
    }

    // 3. 确定目标 Bin（由 RenderState 中的 CullBinAttrib 决定）
    int bin_index = object._state->get_bin_index();
    CullBin *bin = get_bin(bin_index);

    // 4. Munge 顶点数据（格式转换，适配 GSG 要求）
    object.munge_geom(_gsg, _gsg->get_geom_munger(object._state, ...), ...);

    // 5. 放入 Bin
    bin->add_object(alloc_object(std::move(object)), current_thread);
}
```

### 6.3 内置 Bin 类型

| Bin 类型 | 类 | 排序方式 | 典型用途 |
|----------|-----|----------|----------|
| `unsorted` | [`CullBinUnsorted`](panda/src/cull/cullBinUnsorted.cxx) | 不排序 | 不透明几何体（默认） |
| `state_sorted` | [`CullBinStateSorted`](panda/src/cull/cullBinStateSorted.cxx) | 按 RenderState 排序 | 减少状态切换 |
| `back_to_front` | [`CullBinBackToFront`](panda/src/cull/cullBinBackToFront.cxx) | 从远到近 | 透明物体 |
| `front_to_back` | [`CullBinFrontToBack`](panda/src/cull/cullBinFrontToBack.cxx) | 从近到远 | Early-Z 优化 |
| `fixed` | [`CullBinFixed`](panda/src/cull/cullBinFixed.cxx) | 固定顺序 | GUI、HUD |

### 6.4 `CullResult::finish_cull()` — 排序

**源码位置：** [`cullResult.cxx:265`](panda/src/pgraph/cullResult.cxx:265)

```cpp
void CullResult::finish_cull(SceneSetup *scene_setup, Thread *current_thread) {
    for each bin:
        if (bin_manager->get_bin_active(i))
            bin->finish_cull(scene_setup, current_thread);  // 触发排序
}
```

以 `CullBinStateSorted` 为例：

```cpp
// cullBinStateSorted.cxx:47
void CullBinStateSorted::finish_cull(SceneSetup *, Thread *current_thread) {
    sort(_objects.begin(), _objects.end());  // 按 RenderState 指针排序
}
```

---

## 7. 阶段五：Draw 阶段 — 提交 GPU 绘制命令

### 7.1 `do_draw()` — Draw 阶段入口

**源码位置：** [`graphicsEngine.cxx:2042`](panda/src/display/graphicsEngine.cxx:2042)

```cpp
void GraphicsEngine::do_draw(GraphicsOutput *win, GraphicsStateGuardian *gsg,
                              DisplayRegion *dr, Thread *current_thread) {
    // 1. 从 DisplayRegion 的 Pipeline Cycler 读取 Cull 结果
    PT(CullResult) cull_result = cdata->_cull_result;
    PT(SceneSetup) scene_setup = cdata->_scene_setup;

    // 2. 设置 DisplayRegion（视口、裁剪矩形）
    gsg->prepare_display_region(&dr_reader);

    // 3. 清除缓冲区（如果需要）
    if (dr_reader.is_any_clear_active())
        gsg->clear(dr_reader.get_object());

    // 4. 设置场景（投影矩阵等）
    gsg->set_scene(scene_setup);

    // 5. 开始场景绘制
    if (gsg->begin_scene()) {
        cull_result->draw(current_thread);  // 按 Bin 顺序绘制
        gsg->end_scene();
    }
}
```

### 7.2 `CullResult::draw()` — 按 Bin 顺序绘制

**源码位置：** [`cullResult.cxx:287`](panda/src/pgraph/cullResult.cxx:287)

```cpp
void CullResult::draw(Thread *current_thread) {
    CullBinManager *bin_manager = CullBinManager::get_global_ptr();
    int num_bins = bin_manager->get_num_bins();

    // 按 CullBinManager 定义的全局顺序遍历所有 Bin
    for (int i = 0; i < num_bins; i++) {
        int bin_index = bin_manager->get_bin(i);
        if (_bins[bin_index] != nullptr) {
            _gsg->push_group_marker(_bins[bin_index]->get_name());
            _bins[bin_index]->draw(force, current_thread);  // 绘制单个 Bin
            _gsg->pop_group_marker();
        }
    }
}
```

### 7.3 `CullBin::draw()` → `CullableObject::draw()`

以 `CullBinStateSorted` 为例：

```cpp
// cullBinStateSorted.cxx:57
void CullBinStateSorted::draw(bool force, Thread *current_thread) {
    for (const ObjectData &data : _objects) {
        data._object->draw(_gsg, force, current_thread);
    }
}
```

**`CullableObject::draw()`** 最终调用 GSG：

```cpp
// CullableObject 内部（简化）
void CullableObject::draw(GraphicsStateGuardianBase *gsg, bool force, Thread *thread) {
    // 1. 设置渲染状态和变换矩阵
    gsg->set_state_and_transform(_state, _internal_transform);

    // 2. 开始绘制图元
    gsg->begin_draw_primitives(geom_reader, data_reader, num_instances, force);

    // 3. 按图元类型分发
    for each primitive in geom:
        primitive->draw(gsg, force);  // 调用 draw_triangles / draw_lines 等

    // 4. 结束绘制
    gsg->end_draw_primitives();
}
```

---

## 8. 阶段六：状态管理 — `RenderState` & GSG

### 8.1 `RenderState` — 不可变状态集合

**源码位置：** [`renderState.cxx`](panda/src/pgraph/renderState.cxx)

```
RenderState（全局缓存，引用计数）
  ├─ _attributes[slot] → RenderAttrib*
  │    ├─ ShaderAttrib      (slot 0)  ← 着色器
  │    ├─ TextureAttrib     (slot 1)  ← 纹理
  │    ├─ ColorAttrib       (slot 2)  ← 颜色
  │    ├─ TransparencyAttrib(slot 3)  ← 透明度
  │    ├─ DepthTestAttrib   (slot 4)  ← 深度测试
  │    ├─ DepthWriteAttrib  (slot 5)  ← 深度写入
  │    ├─ CullFaceAttrib    (slot 6)  ← 面剔除
  │    ├─ LightAttrib       (slot 7)  ← 光照
  │    ├─ MaterialAttrib    (slot 8)  ← 材质
  │    ├─ FogAttrib         (slot 9)  ← 雾效
  │    ├─ StencilAttrib     (slot 10) ← 模板测试
  │    ├─ ColorBlendAttrib  (slot 11) ← 混合
  │    └─ CullBinAttrib     (slot 12) ← Bin 分配
  └─ _bin_index             ← 预计算的 Bin 索引
```

**`RenderState::compose()`** 实现状态继承（子节点覆盖父节点）：

```cpp
// 场景图遍历时，每个节点的状态 = 父状态.compose(本节点状态)
CPT(RenderState) child_state = parent_state->compose(node_state);
```

### 8.2 GSG `set_state_and_transform()` — 状态差量更新

**源码位置：** [`glGraphicsStateGuardian_src.cxx:12760`](panda/src/glstuff/glGraphicsStateGuardian_src.cxx:12760)

```cpp
void CLP(GraphicsStateGuardian)::set_state_and_transform(
        const RenderState *target, const TransformState *transform) {

    // 1. 变换矩阵变化 → 更新 ModelView Matrix
    if (transform != _internal_transform) {
        _internal_transform = transform;
        do_issue_transform();  // glUniformMatrix4fv / glLoadMatrixf
    }

    // 2. 状态未变化 → 直接返回（关键优化）
    if (target == _state_rs && _state_mask.is_all_on()) {
        // 仅更新 Shader 的 transform uniform
        if (_current_shader_context)
            _current_shader_context->set_state_and_transform(...);
        return;
    }

    // 3. 确定目标 Shader
    determine_target_shader();

    // 4. Shader 变化 → 切换 Shader Program
    if (_target_shader != _state_shader) {
        do_issue_shader();  // glUseProgram
    }

    // 5. 更新 Shader Uniforms
    if (_current_shader_context)
        _current_shader_context->set_state_and_transform(target, transform, ...);

    // 6. 逐属性差量更新（仅更新变化的属性）
    if (alpha_test changed)    do_issue_alpha_test();
    if (antialias changed)     do_issue_antialias();
    if (clip_plane changed)    do_issue_clip_plane();
    if (color changed)         do_issue_color();
    if (cull_face changed)     do_issue_cull_face();
    if (depth_test changed)    do_issue_depth_test();
    if (depth_write changed)   do_issue_depth_write();
    if (texture changed)       do_issue_texture();
    if (blending changed)      do_issue_blending();
    if (light changed)         do_issue_light();
    if (stencil changed)       do_issue_stencil();
    if (fog changed)           do_issue_fog();
    if (scissor changed)       do_issue_scissor();

    _state_rs = target;  // 记录当前状态
}
```

**`_state_mask` 位图**：每个 slot 对应一位，标记该属性是否已同步到 GPU。

---

## 9. 阶段七：Shader 管线

### 9.1 Shader 绑定流程

```
RenderState 包含 ShaderAttrib
  └─ ShaderAttrib::has_shader() == true
       └─ GSG::determine_target_shader()
            ├─ 有显式 Shader → 直接使用
            └─ auto_shader() == true → ShaderGenerator::synthesize_shader()
                 └─ 根据 LightAttrib / MaterialAttrib / TextureAttrib 自动生成 GLSL
```

**源码位置：** [`glGraphicsStateGuardian_src.cxx:12798`](panda/src/glstuff/glGraphicsStateGuardian_src.cxx:12798)

```cpp
// 确定目标 Shader（在 set_state_and_transform 内调用）
determine_target_shader();

// Shader 切换
if (_target_shader != _state_shader) {
    do_issue_shader();   // → glUseProgram(shader_context->_glsl_program)
    _state_shader = _target_shader;
    // 纹理 slot 需要重新绑定
    _state_mask.clear_bit(TextureAttrib::get_class_slot());
}
```

### 9.2 Shader Uniform 更新

**源码位置：** [`glShaderContext_src.cxx`](panda/src/glstuff/glShaderContext_src.cxx)

```cpp
// ShaderContext::set_state_and_transform() 内部
void CLP(ShaderContext)::set_state_and_transform(
        const RenderState *target,
        const TransformState *modelview,
        const TransformState *camera,
        const TransformState *projection) {

    // 遍历 Shader 声明的所有 matrix spec
    for (Shader::ShaderMatSpec &spec : _shader->_mat_spec) {
        // 从 GSG 获取矩阵值（ModelView / Projection / MVP / Normal 等）
        const LVecBase4f *val = gsg->fetch_specified_value(spec, cache, scratch);
        // 上传到 GPU
        glUniform4fv(spec._id._seqno, spec._array_count, val->get_data());
    }

    // 遍历纹理 spec
    for (Shader::ShaderTexSpec &spec : _shader->_tex_spec) {
        Texture *tex = gsg->fetch_specified_texture(spec, sampler, view);
        // 绑定纹理单元
        gsg->apply_texture(tex_context);
    }
}
```

### 9.3 ShaderAttrib 的 set_shader_input()

**源码位置：** [`shaderAttrib.h:76`](panda/src/pgraph/shaderAttrib.h:76)

```python
# Python 层用法
node.set_shader(shader)
node.set_shader_input("my_texture", tex)
node.set_shader_input("my_color", LVecBase4f(1, 0, 0, 1))
node.set_shader_input("my_matrix", mat4)
```

对应 C++ 层：[`ShaderInput`](panda/src/pgraph/shaderInput.h) 存储输入值，在 Draw 阶段由 [`ShaderContext::set_state_and_transform()`](panda/src/glstuff/glShaderContext_src.cxx) 上传到 GPU。

---

## 10. 阶段八：帧缓冲翻转 — Flip

**源码位置：** [`graphicsEngine.cxx:1759`](panda/src/display/graphicsEngine.cxx:1759)

```cpp
void GraphicsEngine::flip_windows(const Windows &wlist, Thread *current_thread) {
    // 第一遍：begin_flip（发出交换缓冲命令，不等待）
    for each window:
        if (win->flip_ready())
            win->begin_flip();   // → glXSwapBuffers / SwapBuffers / eglSwapBuffers

    // 第二遍：end_flip（等待交换完成）
    for each window:
        win->end_flip();
}
```

**翻转状态机：**

```
render_frame() 开始
    │
    ▼
FS_draw  ──── 所有线程完成绘制 ────► FS_sync
    │                                    │
    │  (auto_flip=true)                  │ do_flip_frame()
    └────────────────────────────────────►
                                         │
                                         ▼
                                      FS_flip  ──► 下一帧 render_frame()
```

---

## 11. 多线程模型

**源码位置：** [`graphicsEngine.h:206`](panda/src/display/graphicsEngine.h:206)

Panda3D 支持通过 `threading-model` 配置变量控制线程分配：

### 11.1 线程模型字符串格式

```
"cull_name/draw_name"
```

| 模型字符串 | 含义 |
|-----------|------|
| `""` (默认) | 单线程：App 线程执行全部 |
| `"Cull/Draw"` | 三线程：App + Cull 线程 + Draw 线程 |
| `"/Draw"` | 两线程：App+Cull 合并，独立 Draw 线程 |
| `"-"` | cull+draw together（无 Bin 排序） |

### 11.2 WindowRenderer 任务分配

**源码位置：** [`graphicsEngine.h:281`](panda/src/display/graphicsEngine.h:281)

```
WindowRenderer
  ├─ _window  → 处理窗口事件（resize/move）
  ├─ _cull    → 执行 Cull 阶段（cull_to_bins）
  ├─ _draw    → 执行 Draw 阶段（draw_bins）
  └─ _cdraw   → Cull+Draw 合并（cull_and_draw_together）
```

### 11.3 线程同步机制

```cpp
// App 线程通知 Cull/Draw 线程开始新帧
thread->_thread_state = TS_do_frame;
thread->_cv_start.notify();

// App 线程等待所有线程完成
while (thread->_thread_state != TS_wait)
    thread->_cv_done.wait();
```

**Pipeline Cycler** 保证多线程下的数据安全：
- App 线程写入 stage 0
- Cull 线程读取 stage 1（上一帧 App 写入的数据）
- Draw 线程读取 stage 2（上一帧 Cull 写入的数据）
- `_pipeline->cycle()` 在帧末推进所有 stage

---

## 12. 完整调用链汇总

### 12.1 单线程模式（默认）

```
GraphicsEngine::render_frame()                    [graphicsEngine.cxx:713]
  └─ _app.do_frame()                              [graphicsEngine.cxx:2679]
       ├─ cull_and_draw_together(wlist)            [graphicsEngine.cxx:1349]
       │    └─ for each DisplayRegion:
       │         cull_and_draw_together(win, dr)   [graphicsEngine.cxx:1412]
       │           ├─ setup_scene()                [graphicsEngine.cxx:1909]
       │           ├─ gsg->prepare_display_region()
       │           ├─ gsg->set_scene()
       │           ├─ gsg->begin_scene()
       │           ├─ DrawCullHandler cull_handler(gsg)
       │           ├─ dr->do_cull(&cull_handler, scene_setup, gsg)
       │           │    └─ CullTraverser::traverse(scene_root)
       │           │         └─ do_traverse(data)  [cullTraverser.cxx:178]
       │           │              ├─ data.apply_transform_and_state()
       │           │              ├─ node->add_for_draw()  ← GeomNode 提交
       │           │              │    └─ DrawCullHandler::record_object()
       │           │              │         └─ CullableObject::draw()
       │           │              │              ├─ gsg->set_state_and_transform()
       │           │              │              ├─ gsg->begin_draw_primitives()
       │           │              │              ├─ gsg->draw_triangles()
       │           │              │              │    └─ glDrawRangeElements()
       │           │              │              └─ gsg->end_draw_primitives()
       │           │              └─ 递归子节点
       │           └─ gsg->end_scene()
       └─ flip_windows()
```

### 12.2 多线程模式（Cull/Draw 分离）

```
App 线程                          Cull 线程                    Draw 线程
─────────────────────────────     ──────────────────────────   ──────────────────────────
render_frame()                    (等待 TS_do_frame 信号)       (等待 TS_do_frame 信号)
  └─ _pipeline->cycle()
  └─ 通知 Cull/Draw 线程
                                  cull_to_bins(wlist)           draw_bins(wlist)
                                    └─ for each DR:               └─ for each DR:
                                         setup_scene()                 do_draw(win,gsg,dr)
                                         BinCullHandler handler          └─ 读取 CullResult
                                         dr->do_cull(&handler,...)       └─ gsg->begin_scene()
                                           └─ CullTraverser::             └─ cull_result->draw()
                                               traverse()                      └─ CullBin::draw()
                                                 └─ do_traverse()                  └─ CullableObject::draw()
                                                      └─ BinCullHandler::              ├─ set_state_and_transform()
                                                          record_object()               ├─ begin_draw_primitives()
                                                            └─ CullResult::             ├─ draw_triangles()
                                                                add_object()            │    └─ glDrawRangeElements()
                                                                  └─ CullBin::          └─ end_draw_primitives()
                                                                      add_object()
                                         cull_result->finish_cull()
                                           └─ CullBin::finish_cull()
                                                └─ sort()
                                         dr->set_cull_result(cull_result)
```

### 12.3 关键数据流

```
场景图 (PandaNode 树)
    │
    │ CullTraverser::do_traverse()
    │ 累积 TransformState + RenderState
    ▼
CullableObject { _geom, _state, _internal_transform, _instances }
    │
    │ BinCullHandler::record_object()
    │ CullResult::add_object()  ← 透明度处理、Bin 分配、Munge
    ▼
CullBin[] { unsorted / state_sorted / back_to_front / front_to_back / fixed }
    │
    │ CullBin::finish_cull()  ← 排序
    ▼
CullBin::draw()
    │
    │ CullableObject::draw()
    │ GSG::set_state_and_transform()  ← 差量状态更新
    │ GSG::begin_draw_primitives()    ← 绑定 VAO/VBO
    │ GSG::draw_triangles()           ← glDrawRangeElements / glDrawArrays
    ▼
GPU 帧缓冲
    │
    │ GraphicsOutput::begin_flip() / end_flip()
    ▼
屏幕显示
```

---

## 附录：关键源码文件索引

| 文件 | 路径 | 职责 |
|------|------|------|
| [`graphicsEngine.cxx`](panda/src/display/graphicsEngine.cxx) | `panda/src/display/` | 渲染总控制器，render_frame 入口 |
| [`graphicsEngine.h`](panda/src/display/graphicsEngine.h) | `panda/src/display/` | GraphicsEngine 类声明，线程模型 |
| [`graphicsStateGuardian.cxx`](panda/src/display/graphicsStateGuardian.cxx) | `panda/src/display/` | GSG 基类，状态管理 |
| [`graphicsStateGuardian.h`](panda/src/display/graphicsStateGuardian.h) | `panda/src/display/` | GSG 接口声明 |
| [`displayRegion.h`](panda/src/display/displayRegion.h) | `panda/src/display/` | 渲染区域，持有 Camera 和 CullResult |
| [`cullTraverser.cxx`](panda/src/pgraph/cullTraverser.cxx) | `panda/src/pgraph/` | 场景图遍历，视锥剔除 |
| [`cullTraverserData.h`](panda/src/pgraph/cullTraverserData.h) | `panda/src/pgraph/` | 遍历时的累积状态 |
| [`cullResult.cxx`](panda/src/pgraph/cullResult.cxx) | `panda/src/pgraph/` | Cull 结果，Bin 管理 |
| [`renderState.cxx`](panda/src/pgraph/renderState.cxx) | `panda/src/pgraph/` | 不可变渲染状态，全局缓存 |
| [`shaderAttrib.h`](panda/src/pgraph/shaderAttrib.h) | `panda/src/pgraph/` | Shader 属性，输入管理 |
| [`binCullHandler.cxx`](panda/src/cull/binCullHandler.cxx) | `panda/src/cull/` | 多线程 Cull Handler |
| [`drawCullHandler.cxx`](panda/src/cull/drawCullHandler.cxx) | `panda/src/cull/` | 单线程 Cull+Draw Handler |
| [`cullBinStateSorted.cxx`](panda/src/cull/cullBinStateSorted.cxx) | `panda/src/cull/` | 按状态排序的 Bin |
| [`glGraphicsStateGuardian_src.cxx`](panda/src/glstuff/glGraphicsStateGuardian_src.cxx) | `panda/src/glstuff/` | OpenGL GSG 实现，draw_triangles |
| [`glShaderContext_src.cxx`](panda/src/glstuff/glShaderContext_src.cxx) | `panda/src/glstuff/` | GLSL Shader 上下文，Uniform 更新 |