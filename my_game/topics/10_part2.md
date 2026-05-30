
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
