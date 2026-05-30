# 专题10：多线程与同步

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

现代 CPU 拥有多个核心，3D 引擎需要充分利用并行性来提升性能。但多线程引入了新的复杂性：

| 挑战 | 描述 |
|------|------|
| **数据竞争** | 多线程同时读写同一数据，导致未定义行为 |
| **死锁** | 两个线程互相等待对方释放锁 |
| **流水线延迟** | App/Cull/Draw 三阶段流水线需要数据隔离 |
| **GIL 限制** | Python 的全局解释器锁限制真正的并行 |
| **同步开销** | 锁的获取/释放本身有性能代价 |
| **内存可见性** | CPU 缓存导致一个线程的写入对另一个线程不可见 |

Panda3D 的多线程架构核心是**流水线循环器**（PipelineCycler）：通过为每个流水线阶段维护独立的数据副本，实现无锁的阶段间数据传递。

---

## 2. 数学原理

### 2.1 流水线并行性

**串行执行**（单线程）：
```
帧 N:   [App] → [Cull] → [Draw]
帧 N+1:                           [App] → [Cull] → [Draw]
时间:   |----T_app----|----T_cull----|----T_draw----|
总时间 = T_app + T_cull + T_draw
```

**流水线执行**（多线程）：
```
帧 N:   [App_N] → [Cull_N] → [Draw_N]
帧 N+1:           [App_N+1] → [Cull_N+1] → [Draw_N+1]
帧 N+2:                       [App_N+2] → [Cull_N+2] → [Draw_N+2]
时间:   |--T--|--T--|--T--|--T--|--T--|--T--|
吞吐量 = 1帧 / max(T_app, T_cull, T_draw)
```

**加速比**（Amdahl 定律）：
```
S(n) = 1 / (s + (1-s)/n)

其中：
  s = 串行部分比例（无法并行化）
  n = 处理器数量
  1-s = 可并行化部分

当 n→∞ 时，S_max = 1/s
```

对于 3D 引擎，App 阶段（游戏逻辑）通常是串行瓶颈，Cull 和 Draw 可以并行。

### 2.2 内存模型与可见性

**CPU 缓存层次**：
```
CPU Core 0          CPU Core 1
  L1 Cache (32KB)     L1 Cache (32KB)
  L2 Cache (256KB)    L2 Cache (256KB)
  ↓                   ↓
  L3 Cache (共享, 8MB)
  ↓
  主内存 (RAM)
```

**内存屏障**（Memory Barrier）：确保内存操作的顺序性和可见性：
- `store-store barrier`：确保写操作按顺序执行
- `load-load barrier`：确保读操作按顺序执行
- `full barrier`：确保所有内存操作的顺序

**C++ 原子操作**（`std::atomic`）：
```cpp
std::atomic<int> counter{0};
counter.fetch_add(1, std::memory_order_relaxed);  // 无序原子加
counter.store(42, std::memory_order_release);      // 释放语义
int val = counter.load(std::memory_order_acquire); // 获取语义
```

### 2.3 锁的性能模型

**互斥锁（Mutex）的代价**：
```
无竞争时：~20-50 ns（系统调用开销）
有竞争时：~1-10 μs（线程切换开销）
```

**自旋锁（Spinlock）的代价**：
```
无竞争时：~5-10 ns（原子操作）
有竞争时：CPU 空转，浪费核心资源
适用场景：临界区极短（< 100 ns）
```

**读写锁（RWLock）**：
```
多读者并发：O(1) 无竞争
写者独占：阻塞所有读者
适用场景：读多写少
```

### 2.4 PipelineCycler 的数据隔离

Panda3D 的核心创新：每个可变数据对象维护 N 个副本（N = 流水线阶段数）：

```
阶段 0 (App):   [数据副本 0] ← App 线程写入
阶段 1 (Cull):  [数据副本 1] ← Cull 线程读取（上一帧 App 写入的数据）
阶段 2 (Draw):  [数据副本 2] ← Draw 线程读取（上上帧 App 写入的数据）

每帧结束时，Pipeline::cycle() 将副本向后移动一位：
  副本 2 ← 副本 1 ← 副本 0
```

**优势**：App 和 Cull/Draw 线程可以同时运行，无需锁（因为它们访问不同的副本）。

**代价**：数据有 1-2 帧的延迟（Draw 线程看到的是 1-2 帧前的数据）。

---

## 3. 工程实践

### 3.1 Panda3D 的线程模型

通过 `threading-model` 配置控制：

| 模式 | 描述 | 适用场景 |
|------|------|---------|
| `""` (空) | 单线程，App/Cull/Draw 全在主线程 | 调试、简单场景 |
| `"cull/draw"` | Cull 和 Draw 在独立线程 | 多核 CPU，复杂场景 |
| `"draw"` | 只有 Draw 在独立线程 | 中等复杂度 |
| `"cull/draw/app"` | 三阶段完全分离 | 高性能需求 |

**配置方式**：
```
# config.prc
threading-model cull/draw
```

### 3.2 任务系统（Task Manager）

Panda3D 的 `AsyncTaskManager` 是一个**协作式多任务**系统：

```
主线程（App 线程）
  ├── taskMgr.step()  ← 每帧调用
  │   ├── 执行所有 sort < 0 的任务（输入处理）
  │   ├── 执行所有 sort = 0 的任务（游戏逻辑）
  │   ├── 执行所有 sort > 0 的任务（渲染更新）
  │   └── 执行 igLoop（触发渲染）
  └── 等待渲染完成（若多线程）
```

**任务优先级**（sort 值）：
```python
# 内置任务的 sort 值
SORT_INPUT    = -40   # 输入处理
SORT_RESET    = -30   # 重置状态
SORT_PHYSICS  = -20   # 物理更新
SORT_ANIM     = -10   # 动画更新
SORT_GAME     =   0   # 游戏逻辑（默认）
SORT_AUDIO    =  60   # 音频更新
SORT_RENDER   =  50   # 渲染（igLoop）
```

### 3.3 Python 多线程的限制

Python 的 GIL（Global Interpreter Lock）限制了真正的 Python 并行：

```
GIL 规则：
  - 同一时刻只有一个 Python 线程执行字节码
  - I/O 操作会释放 GIL（允许其他线程运行）
  - C 扩展可以释放 GIL（Panda3D 的 C++ 代码可以并行）
```

**Panda3D 的解决方案**：
- 游戏逻辑在主线程（Python）
- Cull/Draw 在 C++ 线程（不受 GIL 限制）
- 使用 `Thread.consider_yield()` 主动让出 GIL

### 3.4 线程安全的数据访问

**CycleDataReader/Writer 模式**：

```cpp
// 读取（线程安全）
{
    CDReader cdata(_cycler);  // 获取当前阶段的只读指针
    int value = cdata->_my_value;
}  // 析构时自动释放

// 写入（线程安全）
{
    CDWriter cdata(_cycler);  // 获取当前阶段的可写指针
    cdata->_my_value = 42;
}  // 析构时自动标记为脏数据
```

---

## 4. Panda3D 源码剖析

### 4.1 Pipeline 流水线管理器

**文件**：[`pipeline.h`](panda/src/pipeline/pipeline.h)

```cpp
// pipeline.h:38
class EXPCL_PANDA_PIPELINE Pipeline : public Namable {
public:
  // 获取全局渲染流水线（单例）
  static Pipeline *get_render_pipeline();

  // 推进流水线（每帧调用，将数据副本向后移动）
  void cycle();

  // 设置流水线阶段数（1=单线程，2=双缓冲，3=三缓冲）
  void set_num_stages(int num_stages);
  int get_num_stages() const;

  // 注册/注销 PipelineCycler（内部使用）
  void add_cycler(PipelineCyclerTrueImpl *cycler);
  void add_dirty_cycler(PipelineCyclerTrueImpl *cycler);
  void remove_cycler(PipelineCyclerTrueImpl *cycler);

  // 统计
  int get_num_cyclers() const;
  int get_num_dirty_cyclers() const;

private:
  int _num_stages;
  static Pipeline *_render_pipeline;

  // 干净的循环器链表（未修改的数据）
  PipelineCyclerLinks _clean;
  // 脏的循环器链表（已修改，需要在 cycle() 时传播）
  PipelineCyclerLinks _dirty;
};
```

**`cycle()` 的工作原理**：

```
Pipeline::cycle()
  ├── 遍历所有脏的 PipelineCycler
  │   └── 将阶段 0 的数据复制到阶段 1（若有 2 个阶段）
  │       或复制到阶段 1 和 2（若有 3 个阶段）
  └── 清空脏列表
```

### 4.2 PipelineCycler 数据循环器

**文件**：[`pipelineCycler.h`](panda/src/pipeline/pipelineCycler.h)

```cpp
// pipelineCycler.h:45
template<class CycleDataType>
struct PipelineCycler : public PipelineCyclerBase {
public:
  // 读取当前阶段的数据（只读）
  const CycleDataType *read(Thread *current_thread) const;

  // 写入当前阶段的数据（可写，标记为脏）
  CycleDataType *write(Thread *current_thread);

  // 写入并向上游传播（确保所有阶段都更新）
  CycleDataType *write_upstream(bool force_to_0, Thread *current_thread);

  // 读取特定阶段的数据（用于 Draw 线程读取 Cull 阶段的数据）
  const CycleDataType *read_stage(int pipeline_stage, Thread *current_thread) const;

  // 直接访问（不安全，仅用于调试）
  CycleDataType *cheat() const;

private:
  // 若未启用流水线：只存储一份数据
  CycleDataType _typed_data;

  // 若启用流水线：存储 N 份数据（N = 流水线阶段数）
  // 实际存储在 PipelineCyclerTrueImpl 中
};
```

**使用示例**（Panda3D 内部代码模式）：

```cpp
class MyNode : public PandaNode {
  // 可变数据放在 CData 中
  class CData : public CycleData {
  public:
    int _position_x = 0;
    int _position_y = 0;
    bool _visible = true;
  };

  // 每个 MyNode 实例有一个 PipelineCycler
  PipelineCycler<CData> _cycler;

public:
  // 读取（App 线程）
  int get_x() const {
    CDReader cdata(_cycler);
    return cdata->_position_x;
  }

  // 写入（App 线程）
  void set_x(int x) {
    CDWriter cdata(_cycler);
    cdata->_position_x = x;
    // CDWriter 析构时自动将此 cycler 加入 Pipeline 的脏列表
  }

  // Draw 线程读取（读取 Draw 阶段的数据，即 1-2 帧前的数据）
  int get_x_for_draw(Thread *current_thread) const {
    CDStageReader cdata(_cycler, 2, current_thread);  // 阶段 2 = Draw
    return cdata->_position_x;
  }
};
```

### 4.3 GraphicsEngine 的线程调度

**文件**：[`graphicsEngine.h`](panda/src/display/graphicsEngine.h)

```cpp
// graphicsEngine.h 中的 WindowRenderer 类
class WindowRenderer {
public:
  // 每个 WindowRenderer 负责一组窗口的特定任务
  Windows _window;  // 窗口管理任务（通常在 App 线程）
  Windows _cull;    // 裁剪任务
  Windows _draw;    // 绘制任务

  // 执行裁剪任务
  void do_cull(GraphicsEngine *engine, Thread *current_thread);

  // 执行绘制任务
  void do_draw(GraphicsEngine *engine, Thread *current_thread);
};

// RenderThread：继承自 WindowRenderer 和 Thread
class RenderThread : public WindowRenderer, public Thread {
public:
  // 线程主循环
  virtual void thread_main();

  // 线程状态（由 App 线程控制）
  ThreadState _thread_state;

  // 同步原语
  ConditionVar _cv_start;  // App 通知线程开始工作
  ConditionVar _cv_done;   // 线程通知 App 工作完成
  Mutex _lock;
};
```

**多线程帧循环**：

```
App 线程（主线程）：
  1. 执行游戏逻辑（Task Manager）
  2. 等待 Cull 线程完成上一帧的裁剪
  3. 通知 Cull 线程开始新一帧的裁剪
  4. 等待 Draw 线程完成上一帧的绘制
  5. 通知 Draw 线程开始新一帧的绘制
  6. Pipeline::cycle()（推进数据副本）

Cull 线程：
  1. 等待 App 线程通知
  2. 遍历场景图，执行视锥裁剪
  3. 将裁剪结果存入 CullResult
  4. 通知 App 线程完成

Draw 线程：
  1. 等待 App 线程通知
  2. 读取 CullResult（上一帧 Cull 的结果）
  3. 发送 OpenGL 命令
  4. 通知 App 线程完成
```

### 4.4 同步原语

**文件**：`panda/src/pipeline/`

```cpp
// Mutex（互斥锁）
class Mutex {
  void acquire();   // 获取锁（阻塞）
  bool try_acquire(); // 尝试获取（非阻塞）
  void release();   // 释放锁
};

// MutexHolder（RAII 锁管理）
class MutexHolder {
  MutexHolder(Mutex &mutex) { mutex.acquire(); }
  ~MutexHolder() { _mutex.release(); }
};

// ReMutex（可重入互斥锁）
class ReMutex {
  // 同一线程可以多次获取，不会死锁
  void acquire();
  void release();
};

// ConditionVar（条件变量）
class ConditionVar {
  void wait();          // 等待（释放锁，阻塞）
  void notify();        // 通知一个等待者
  void notify_all();    // 通知所有等待者
};

// LightMutex（轻量级互斥锁，不支持调试）
class LightMutex {
  // 比 Mutex 更轻量，用于高频临界区
};
```
