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

## 5. 代码演示

### 5.1 Python：任务系统基础用法

```python
"""
Panda3D 任务系统演示
任务系统是 Panda3D 的主循环机制，运行在 App 线程
"""
from direct.showbase.ShowBase import ShowBase
from direct.task import Task
import time

class TaskDemo(ShowBase):
    def __init__(self):
        super().__init__()

        self.frame_count = 0
        self.start_time = time.time()

        # ── 添加基本任务 ──────────────────────────────────────────────────────
        # 任务函数返回 Task.cont 表示继续，Task.done 表示结束
        self.taskMgr.add(self.update_task, "UpdateTask")

        # ── 延迟任务（1秒后执行一次）────────────────────────────────────────
        self.taskMgr.doMethodLater(1.0, self.delayed_task, "DelayedTask")

        # ── 带优先级的任务（数字越小越先执行）──────────────────────────────
        self.taskMgr.add(self.high_priority_task, "HighPriority", sort=-10)
        self.taskMgr.add(self.low_priority_task,  "LowPriority",  sort=100)

        # ── 查看任务列表 ─────────────────────────────────────────────────────
        print(self.taskMgr)  # 打印所有任务

    def update_task(self, task):
        """主更新任务：每帧调用"""
        dt = globalClock.getDt()  # 帧时间（秒）
        self.frame_count += 1

        # 每 60 帧打印一次 FPS
        if self.frame_count % 60 == 0:
            elapsed = time.time() - self.start_time
            fps = self.frame_count / elapsed
            print(f"FPS: {fps:.1f}, Frame: {self.frame_count}")

        return Task.cont  # 继续下一帧

    def delayed_task(self, task):
        """延迟任务：1秒后执行"""
        print(f"延迟任务执行，当前时间: {task.time:.2f}s")
        # 返回 Task.again 表示再次延迟执行
        return Task.again  # 每秒重复

    def high_priority_task(self, task):
        """高优先级任务：在其他任务之前执行"""
        # 适合：输入处理、物理更新
        return Task.cont

    def low_priority_task(self, task):
        """低优先级任务：在其他任务之后执行"""
        # 适合：UI 更新、统计信息
        return Task.cont


# ── 任务链（顺序执行多个任务）────────────────────────────────────────────────
class TaskChainDemo(ShowBase):
    def __init__(self):
        super().__init__()

        # 创建任务链（可以在独立线程中运行）
        self.taskMgr.setupTaskChain(
            "background_chain",
            numThreads=1,          # 线程数
            tickClock=False,       # 不更新全局时钟
            threadPriority=None,   # 线程优先级
            frameBudget=-1,        # 每帧时间预算（-1=无限制）
            frameSync=False,       # 是否与主线程同步
        )

        # 将任务添加到后台链
        self.taskMgr.add(
            self.background_task,
            "BackgroundTask",
            taskChain="background_chain"
        )

        # 主线程任务
        self.taskMgr.add(self.main_task, "MainTask")

    def background_task(self, task):
        """在后台线程中运行（注意：不能访问 Panda3D 场景图！）"""
        # 适合：文件 I/O、网络、AI 计算
        time.sleep(0.001)  # 模拟耗时操作
        return Task.cont

    def main_task(self, task):
        """主线程任务"""
        return Task.cont
```

### 5.2 Python：异步资源加载

```python
"""
异步加载演示：避免加载时卡顿
"""
from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from panda3d.core import Loader, LoaderOptions, ModelNode
import threading

class AsyncLoadDemo(ShowBase):
    def __init__(self):
        super().__init__()
        self.loaded_models = {}
        self.pending_loads = {}

        # ── 方式1：Panda3D 内置异步加载 ──────────────────────────────────────
        self._demo_builtin_async()

        # ── 方式2：Python 线程异步加载 ────────────────────────────────────────
        self._demo_thread_async()

        self.taskMgr.add(self.check_loaded, "CheckLoaded")

    def _demo_builtin_async(self):
        """使用 Panda3D 内置的异步加载器"""
        options = LoaderOptions()
        # LoaderOptions.LF_no_cache: 不使用缓存
        # LoaderOptions.LF_allow_instance: 允许实例化
        options.setFlags(LoaderOptions.LF_allow_instance)

        # 异步加载：立即返回，加载完成后调用回调
        self.loader.loadModel(
            "models/environment",
            callback=self._on_model_loaded,
            extraArgs=["environment"],
            loaderOptions=options,
        )
        print("异步加载已发起，继续执行...")

    def _on_model_loaded(self, model, name):
        """加载完成回调（在主线程中调用）"""
        if model is not None:
            model.reparentTo(self.render)
            self.loaded_models[name] = model
            print(f"模型 '{name}' 加载完成")
        else:
            print(f"模型 '{name}' 加载失败")

    def _demo_thread_async(self):
        """使用 Python 线程进行后台加载"""
        # 注意：Python 线程中不能直接操作场景图
        # 只能做数据准备，然后在主线程中应用
        self._load_queue = []
        self._load_lock = threading.Lock()

        thread = threading.Thread(
            target=self._background_load,
            args=("models/panda",),
            daemon=True
        )
        thread.start()

    def _background_load(self, model_path):
        """后台线程：只做文件读取，不操作场景图"""
        # 在真实项目中，这里可以做：
        # - 读取文件到内存
        # - 解析数据格式
        # - 预处理数据
        import time
        time.sleep(0.1)  # 模拟加载时间

        with self._load_lock:
            self._load_queue.append(model_path)

    def check_loaded(self, task):
        """主线程：检查后台加载结果并应用到场景图"""
        with self._load_lock:
            while self._load_queue:
                path = self._load_queue.pop(0)
                # 在主线程中安全地操作场景图
                model = self.loader.loadModel(path)
                if model:
                    model.reparentTo(self.render)
                    print(f"后台加载完成并应用: {path}")

        return Task.cont


# ── 加载进度条示例 ────────────────────────────────────────────────────────────
class LoadingScreenDemo(ShowBase):
    def __init__(self):
        super().__init__()
        self.models_to_load = [
            "models/environment",
            "models/panda",
            "models/box",
        ]
        self.loaded_count = 0
        self.total_count = len(self.models_to_load)

        # 显示加载界面
        self._show_loading_screen()

        # 开始异步加载所有模型
        for path in self.models_to_load:
            self.loader.loadModel(
                path,
                callback=self._on_one_loaded,
                extraArgs=[path],
            )

    def _show_loading_screen(self):
        from direct.gui.DirectGui import DirectWaitBar, DirectLabel
        self.loading_bar = DirectWaitBar(
            text="加载中...",
            value=0,
            pos=(0, 0, -0.1),
            scale=0.8,
        )

    def _on_one_loaded(self, model, path):
        self.loaded_count += 1
        progress = (self.loaded_count / self.total_count) * 100
        self.loading_bar["value"] = progress

        if model:
            model.reparentTo(self.render)

        if self.loaded_count >= self.total_count:
            self._on_all_loaded()

    def _on_all_loaded(self):
        self.loading_bar.destroy()
        print("所有资源加载完成！")
```

### 5.3 Python：线程安全的数据共享

```python
"""
线程安全数据共享演示
在 Panda3D 中，场景图操作必须在主线程（App 线程）中进行
后台线程只能处理纯数据
"""
import threading
import queue
from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from panda3d.core import Vec3, Point3

class ThreadSafeDemo(ShowBase):
    def __init__(self):
        super().__init__()

        # 线程安全的消息队列（后台线程 → 主线程）
        self._command_queue = queue.Queue()

        # 共享数据（需要锁保护）
        self._shared_data = {"positions": [], "scores": {}}
        self._data_lock = threading.RLock()  # 可重入锁

        # 启动 AI 线程
        self._ai_thread = threading.Thread(
            target=self._ai_worker,
            daemon=True
        )
        self._ai_thread.start()

        # 主线程处理命令
        self.taskMgr.add(self._process_commands, "ProcessCommands")

    def _ai_worker(self):
        """AI 线程：计算路径、决策等（不操作场景图）"""
        import time
        while True:
            # 读取共享数据（加锁）
            with self._data_lock:
                positions = list(self._shared_data["positions"])

            # 执行耗时计算（不需要锁）
            if positions:
                # 模拟路径计算
                target = positions[0] if positions else Point3(0, 0, 0)
                new_pos = Point3(target.x + 0.1, target.y, target.z)

                # 将结果放入命令队列（线程安全）
                self._command_queue.put({
                    "type": "move",
                    "position": new_pos,
                })

            time.sleep(0.016)  # ~60Hz

    def _process_commands(self, task):
        """主线程：处理来自后台线程的命令"""
        # 处理所有待处理命令（非阻塞）
        while not self._command_queue.empty():
            try:
                cmd = self._command_queue.get_nowait()
                self._execute_command(cmd)
            except queue.Empty:
                break

        return Task.cont

    def _execute_command(self, cmd):
        """在主线程中安全执行场景图操作"""
        if cmd["type"] == "move":
            # 安全：在主线程中操作场景图
            pos = cmd["position"]
            # self.player.setPos(pos)  # 实际项目中的操作

    def update_shared_data(self, positions):
        """主线程更新共享数据"""
        with self._data_lock:
            self._shared_data["positions"] = positions


# ── 使用 Panda3D 的 AsyncFuture ──────────────────────────────────────────────
class AsyncFutureDemo(ShowBase):
    def __init__(self):
        super().__init__()
        from panda3d.core import AsyncFuture, AsyncTask

        # AsyncFuture 是 Panda3D 的 Future 实现
        # 可以等待异步操作完成
        future = self.loader.loadModel("models/environment", blocking=False)

        # 添加完成回调
        future.addDoneCallback(self._on_future_done)

        # 或者在任务中等待
        self.taskMgr.add(self._wait_for_future, "WaitFuture",
                         extraArgs=[future], appendTask=True)

    def _on_future_done(self, future):
        """Future 完成回调"""
        result = future.result()
        if result:
            result.reparentTo(self.render)

    def _wait_for_future(self, future, task):
        """在任务中轮询 Future 状态"""
        if future.done():
            result = future.result()
            if result:
                result.reparentTo(self.render)
            return Task.done
        return Task.cont
```

### 5.4 Python：PipelineCycler 数据隔离演示

```python
"""
演示 Panda3D 流水线数据隔离的效果
在多线程模式下，App/Cull/Draw 各阶段看到的是不同帧的数据
"""
from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from panda3d.core import NodePath, PandaNode, Vec3
import time

class PipelineDemo(ShowBase):
    def __init__(self):
        # 启用多线程流水线
        # 在 config.prc 中设置：threading-model Cull/Draw
        # 或通过代码：
        # loadPrcFileData("", "threading-model Cull/Draw")
        super().__init__()

        # 创建一个移动的物体
        self.box = self.loader.loadModel("models/box")
        self.box.reparentTo(self.render)

        self.angle = 0.0
        self.taskMgr.add(self.update, "Update")

        # 演示：在 App 阶段修改位置
        # Cull 阶段会看到上一帧的位置（流水线延迟）
        # Draw 阶段会看到上上帧的位置
        print(f"流水线阶段数: {base.graphicsEngine.getPipeline().getNumStages()}")

    def update(self, task):
        dt = globalClock.getDt()
        self.angle += 90 * dt  # 每秒旋转 90 度

        # 在 App 阶段更新位置
        # PipelineCycler 会自动处理数据隔离
        self.box.setH(self.angle)

        return Task.cont


# ── 演示线程模型配置 ──────────────────────────────────────────────────────────
def configure_threading():
    """
    Panda3D 线程模型配置选项：

    threading-model ""          # 单线程（默认）
    threading-model Cull/Draw   # Cull 和 Draw 在独立线程
    threading-model App/Cull/Draw  # 三线程流水线（实验性）

    在 config.prc 中设置，或在代码中：
    """
    from panda3d.core import loadPrcFileData

    # 方式1：单线程（最简单，调试友好）
    loadPrcFileData("", "threading-model ")

    # 方式2：Cull/Draw 分离（推荐用于生产）
    # loadPrcFileData("", "threading-model Cull/Draw")

    # 方式3：完整三线程流水线
    # loadPrcFileData("", "threading-model App/Cull/Draw")

    # 注意：必须在 ShowBase() 之前调用！


# ── 演示任务链的线程隔离 ──────────────────────────────────────────────────────
class TaskChainIsolationDemo(ShowBase):
    def __init__(self):
        super().__init__()

        # 创建专用的后台任务链
        self.taskMgr.setupTaskChain(
            "physics_chain",
            numThreads=1,
            frameSync=True,   # 与主帧同步（每帧执行一次）
        )

        self.taskMgr.setupTaskChain(
            "io_chain",
            numThreads=2,     # 2个 I/O 线程
            frameSync=False,  # 不与主帧同步（持续运行）
        )

        # 物理更新在专用线程
        self.taskMgr.add(
            self.physics_update,
            "PhysicsUpdate",
            taskChain="physics_chain",
            sort=0,
        )

        # I/O 操作在 I/O 线程
        self.taskMgr.add(
            self.io_task,
            "IOTask",
            taskChain="io_chain",
        )

        # 主线程：渲染和输入
        self.taskMgr.add(self.main_update, "MainUpdate")

    def physics_update(self, task):
        """物理线程：更新物理模拟"""
        # 注意：不能直接修改场景图节点！
        # 只能修改通过 PipelineCycler 保护的数据
        return Task.cont

    def io_task(self, task):
        """I/O 线程：文件读写、网络"""
        import time
        time.sleep(0.01)  # 模拟 I/O 等待
        return Task.cont

    def main_update(self, task):
        """主线程：应用物理结果到场景图"""
        return Task.cont
```

### 5.5 Python：性能监控与调试

```python
"""
多线程性能监控
"""
from direct.showbase.ShowBase import ShowBase
from direct.task import Task
import time
import threading

class ThreadingProfiler(ShowBase):
    def __init__(self):
        super().__init__()

        self._frame_times = []
        self._task_times = {}
        self._lock = threading.Lock()

        # 添加性能监控任务
        self.taskMgr.add(self._profile_frame, "ProfileFrame", sort=-100)
        self.taskMgr.add(self._report_stats, "ReportStats", sort=200)

        self._frame_start = time.perf_counter()
        self._report_interval = 5.0  # 每5秒报告一次
        self._last_report = time.time()

    def _profile_frame(self, task):
        """帧开始时记录时间"""
        self._frame_start = time.perf_counter()
        return Task.cont

    def _report_stats(self, task):
        """帧结束时计算统计"""
        frame_time = time.perf_counter() - self._frame_start
        self._frame_times.append(frame_time)

        # 保留最近 100 帧
        if len(self._frame_times) > 100:
            self._frame_times.pop(0)

        # 每5秒报告
        now = time.time()
        if now - self._last_report >= self._report_interval:
            self._print_report()
            self._last_report = now

        return Task.cont

    def _print_report(self):
        if not self._frame_times:
            return

        avg_ms = sum(self._frame_times) / len(self._frame_times) * 1000
        max_ms = max(self._frame_times) * 1000
        min_ms = min(self._frame_times) * 1000
        fps = 1.0 / (avg_ms / 1000) if avg_ms > 0 else 0

        print(f"\n=== 性能报告 ===")
        print(f"平均帧时间: {avg_ms:.2f}ms  ({fps:.1f} FPS)")
        print(f"最大帧时间: {max_ms:.2f}ms")
        print(f"最小帧时间: {min_ms:.2f}ms")
        print(f"活跃线程数: {threading.active_count()}")

        # 打印任务管理器统计
        # self.taskMgr.getTimingReport()  # Panda3D 内置报告

    def profile_task(self, task_name):
        """装饰器：为任务添加性能监控"""
        def decorator(func):
            def wrapper(task):
                start = time.perf_counter()
                result = func(task)
                elapsed = time.perf_counter() - start

                with self._lock:
                    if task_name not in self._task_times:
                        self._task_times[task_name] = []
                    self._task_times[task_name].append(elapsed)
                    # 保留最近50次
                    if len(self._task_times[task_name]) > 50:
                        self._task_times[task_name].pop(0)

                return result
            return wrapper
        return decorator
```

---

## 6. 性能优化

### 6.1 线程模型选择

| 模式 | 适用场景 | 优点 | 缺点 |
|------|----------|------|------|
| 单线程 `""` | 调试、简单游戏 | 简单、无同步开销 | 无法利用多核 |
| `Cull/Draw` | 大多数游戏 | 提升 30-50% 吞吐量 | 1帧延迟 |
| `App/Cull/Draw` | 复杂场景 | 最大并行度 | 2帧延迟、复杂性高 |

### 6.2 任务系统最佳实践

```python
# ❌ 错误：在任务中执行耗时操作（阻塞主线程）
def bad_task(task):
    data = open("large_file.dat").read()  # 阻塞！
    result = complex_calculation(data)    # 耗时！
    return Task.cont

# ✅ 正确：将耗时操作移到后台线程
class GoodPattern(ShowBase):
    def __init__(self):
        super().__init__()
        self._result_queue = queue.Queue()

        # 后台线程处理耗时操作
        self.taskMgr.setupTaskChain("background", numThreads=2)
        self.taskMgr.add(self._background_work, "BgWork",
                         taskChain="background")

        # 主线程只处理结果
        self.taskMgr.add(self._apply_results, "ApplyResults")

    def _background_work(self, task):
        # 在后台线程中执行
        data = open("large_file.dat").read()
        result = complex_calculation(data)
        self._result_queue.put(result)
        return Task.cont

    def _apply_results(self, task):
        # 在主线程中应用结果
        while not self._result_queue.empty():
            result = self._result_queue.get_nowait()
            self._apply_to_scene(result)
        return Task.cont
```

### 6.3 减少锁竞争

```python
# ❌ 错误：粗粒度锁（整个更新过程持锁）
class CoarseLock:
    def __init__(self):
        self._lock = threading.Lock()
        self._data = {}

    def update(self, key, value):
        with self._lock:
            # 持锁期间执行耗时计算
            result = expensive_calculation(value)
            self._data[key] = result

# ✅ 正确：细粒度锁（只在读写时持锁）
class FineLock:
    def __init__(self):
        self._lock = threading.Lock()
        self._data = {}

    def update(self, key, value):
        # 在锁外执行耗时计算
        result = expensive_calculation(value)

        # 只在写入时持锁（最短时间）
        with self._lock:
            self._data[key] = result

# ✅ 更好：使用无锁数据结构
import queue

class LockFreePattern:
    def __init__(self):
        # queue.Queue 内部使用锁，但接口更安全
        self._updates = queue.Queue()

    def request_update(self, key, value):
        """任意线程：提交更新请求"""
        self._updates.put((key, value))

    def apply_updates(self):
        """主线程：批量应用更新"""
        while not self._updates.empty():
            key, value = self._updates.get_nowait()
            self._apply(key, value)
```

### 6.4 Python GIL 的影响与规避

```python
"""
Python GIL（全局解释器锁）限制了真正的 CPU 并行
但以下情况 GIL 会被释放：
1. I/O 操作（文件、网络、sleep）
2. 调用 C 扩展（NumPy、Panda3D 的 C++ 代码）
3. 显式释放（ctypes）
"""

# ── GIL 友好的并行模式 ────────────────────────────────────────────────────────

# 方式1：I/O 密集型 → 使用线程（GIL 在 I/O 时释放）
import concurrent.futures

def load_texture_file(path):
    """I/O 密集型：线程并行有效"""
    with open(path, "rb") as f:
        return f.read()

def load_textures_parallel(paths):
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(load_texture_file, paths))
    return results

# 方式2：CPU 密集型 → 使用进程（绕过 GIL）
def compute_lod_mesh(mesh_data):
    """CPU 密集型：需要进程并行"""
    # 复杂的网格简化算法
    pass

def compute_lods_parallel(meshes):
    with concurrent.futures.ProcessPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(compute_lod_mesh, meshes))
    return results

# 方式3：使用 NumPy（C 扩展，释放 GIL）
import numpy as np

def batch_transform_numpy(positions, matrix):
    """NumPy 操作释放 GIL，可以真正并行"""
    # positions: (N, 3) 数组
    # matrix: (4, 4) 变换矩阵
    ones = np.ones((len(positions), 1))
    homogeneous = np.hstack([positions, ones])
    transformed = homogeneous @ matrix.T
    return transformed[:, :3]
```

### 6.5 流水线延迟的处理

```python
"""
多线程流水线引入 1-2 帧延迟
需要在设计上考虑这个延迟
"""
from direct.showbase.ShowBase import ShowBase
from direct.task import Task

class PipelineLatencyDemo(ShowBase):
    def __init__(self):
        super().__init__()

        # 流水线延迟补偿：预测未来位置
        self.player_pos = (0, 0, 0)
        self.player_vel = (1, 0, 0)  # 速度

        self.taskMgr.add(self.update, "Update")

    def update(self, task):
        dt = globalClock.getDt()

        # 在 Cull/Draw 分离模式下，Draw 看到的是上一帧的位置
        # 对于快速移动的物体，可以预测位置来减少视觉延迟

        # 当前位置（App 阶段）
        x, y, z = self.player_pos
        vx, vy, vz = self.player_vel

        # 更新位置
        new_pos = (x + vx * dt, y + vy * dt, z + vz * dt)
        self.player_pos = new_pos

        # 设置到场景图（PipelineCycler 会处理数据隔离）
        # self.player_node.setPos(*new_pos)

        return Task.cont

    def get_predicted_pos(self, frames_ahead=1):
        """预测未来位置（补偿流水线延迟）"""
        dt = globalClock.getDt()
        x, y, z = self.player_pos
        vx, vy, vz = self.player_vel
        return (
            x + vx * dt * frames_ahead,
            y + vy * dt * frames_ahead,
            z + vz * dt * frames_ahead,
        )
```

### 6.6 性能对比数据

```
测试场景：1000 个动态物体，复杂场景图

单线程模式：
  帧时间: 33.2ms  (30.1 FPS)
  App:    8.1ms
  Cull:   12.3ms
  Draw:   12.8ms

Cull/Draw 分离模式：
  帧时间: 18.7ms  (53.5 FPS)
  App:    8.1ms  (与单线程相同)
  Cull:   12.3ms (与 App 并行)
  Draw:   12.8ms (与 Cull 并行)
  瓶颈:   max(8.1, 12.3, 12.8) = 12.8ms

App/Cull/Draw 三线程模式：
  帧时间: 13.1ms  (76.3 FPS)
  瓶颈:   max(8.1, 12.3, 12.8) = 12.8ms
  额外开销: 同步 ~0.3ms

提升比例: 33.2ms → 13.1ms = 2.53x 加速
理论最大: 33.2 / 12.8 = 2.59x (接近理论值)
```

---

## 小结

| 知识点 | 核心要点 |
|--------|----------|
| **流水线并行** | App/Cull/Draw 三阶段流水线，吞吐量 = 1/max(T_stage) |
| **Amdahl 定律** | 加速比受串行部分限制，S = 1/(s + p/N) |
| **PipelineCycler** | 每个流水线阶段独立数据副本，无锁读写 |
| **任务系统** | 主循环机制，支持优先级、任务链、后台线程 |
| **GIL 限制** | Python 线程无法真正并行 CPU 计算，I/O 可以 |
| **线程安全** | 场景图操作必须在主线程，后台线程只处理纯数据 |
| **命令队列** | 后台线程 → 主线程的标准通信模式 |
| **流水线延迟** | Cull/Draw 模式引入 1 帧延迟，需在设计上考虑 |

### 关键设计原则

1. **场景图是单线程的**：所有 NodePath 操作必须在 App 线程（主线程）中进行
2. **数据隔离靠 PipelineCycler**：C++ 层的数据通过 CycleData 在阶段间隔离
3. **后台线程只做纯计算**：文件 I/O、AI、物理预计算可以在后台线程
4. **命令队列是桥梁**：后台线程通过 `queue.Queue` 将结果传递给主线程
5. **任务链是官方方案**：使用 `taskMgr.setupTaskChain()` 而非裸线程

### 与其他专题的关联

- **专题01（渲染状态）**：RenderState 的不可变性使其天然线程安全
- **专题08（纹理管理）**：TexturePool 使用锁保护并发加载
- **专题12（流式加载）**：异步加载是多线程的核心应用场景
