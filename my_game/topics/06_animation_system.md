# 专题06：动画系统

## 目录
1. [问题背景](#1-问题背景)
2. [数学原理](#2-数学原理)
   - 2.1 骨骼动画：蒙皮变换
   - 2.2 关键帧插值
   - 2.3 动画混合的数学
   - 2.4 逆运动学（IK）基础
3. [工程实践](#3-工程实践)
   - 3.1 Panda3D 动画架构
   - 3.2 动画绑定（Binding）
   - 3.3 动画混合策略
   - 3.4 帧插值
4. [Panda3D 源码解析](#4-panda3d-源码解析)
   - 4.1 PartBundle 与 AnimBundle
   - 4.2 AnimControl 时间控制
   - 4.3 BlendType 混合类型
   - 4.4 do_update() 更新流程
5. [代码演示](#5-代码演示)
6. [性能分析](#6-性能分析)

---

## 1. 问题背景

动画系统需要解决以下核心问题：

1. **骨骼变换**：如何用少量骨骼控制大量顶点？
2. **关键帧插值**：如何在关键帧之间平滑过渡？
3. **动画混合**：如何同时播放多个动画（如走路+挥手）？
4. **状态机**：如何管理复杂的动画状态转换（站立→走路→跑步）？
5. **IK（逆运动学）**：如何让脚踩在不平地面上？

---

## 2. 数学原理

### 2.1 骨骼动画：蒙皮变换

**骨骼层次**：骨骼形成树形结构，每个骨骼有局部变换矩阵 $M_{local}$。

**骨骼世界变换**：

$$M_{world}(bone_i) = M_{world}(parent_i) \cdot M_{local}(bone_i)$$

**蒙皮变换（Skinning）**：每个顶点受多个骨骼影响，最终位置是加权平均：

$$\mathbf{v}_{final} = \sum_{i=1}^{N} w_i \cdot M_{world}(bone_i) \cdot M_{bind}^{-1}(bone_i) \cdot \mathbf{v}_{bind}$$

其中：
- $\mathbf{v}_{bind}$：绑定姿势（T-pose）中的顶点位置
- $M_{bind}^{-1}(bone_i)$：绑定姿势逆矩阵（将顶点变换到骨骼局部空间）
- $M_{world}(bone_i)$：当前骨骼世界变换
- $w_i$：骨骼权重（$\sum w_i = 1$）

**蒙皮矩阵（Skinning Matrix）**：

$$M_{skin}(bone_i) = M_{world}(bone_i) \cdot M_{bind}^{-1}(bone_i)$$

这个矩阵预先计算好，每帧上传到 GPU（Uniform 数组）。

### 2.2 关键帧插值

**线性插值（LERP）**：

$$\mathbf{v}(t) = (1-t) \cdot \mathbf{v}_0 + t \cdot \mathbf{v}_1, \quad t \in [0, 1]$$

**球面线性插值（SLERP）**（用于四元数旋转）：

$$q(t) = \frac{\sin((1-t)\theta)}{\sin\theta} q_0 + \frac{\sin(t\theta)}{\sin\theta} q_1$$

其中 $\theta = \arccos(q_0 \cdot q_1)$（四元数点积）。

**三次 Hermite 插值（Cubic Hermite）**：

$$\mathbf{v}(t) = (2t^3 - 3t^2 + 1)\mathbf{v}_0 + (t^3 - 2t^2 + t)\mathbf{m}_0 + (-2t^3 + 3t^2)\mathbf{v}_1 + (t^3 - t^2)\mathbf{m}_1$$

其中 $\mathbf{m}_0, \mathbf{m}_1$ 是切线向量（控制曲线形状）。

**Catmull-Rom 样条**：自动从相邻关键帧计算切线：

$$\mathbf{m}_i = \frac{\mathbf{v}_{i+1} - \mathbf{v}_{i-1}}{2}$$

### 2.3 动画混合的数学

**线性混合（BT_linear）**：

$$M_{blend} = \sum_{i} w_i \cdot M_i, \quad \sum w_i = 1$$

**问题**：矩阵线性混合会导致"糖果纸扭曲"（Candy Wrapper Artifact）——旋转 180° 的两个矩阵平均后可能得到零矩阵（完全压缩）。

**归一化线性混合（BT_normalized_linear）**：

1. 分离旋转和缩放：$M_i = R_i \cdot S_i$
2. 线性混合缩放：$S_{blend} = \sum w_i \cdot S_i$
3. 四元数 SLERP 混合旋转：$q_{blend} = \text{SLERP}(q_0, q_1, w_1)$
4. 重组：$M_{blend} = R_{blend} \cdot S_{blend}$

**组件式混合（BT_componentwise_quat）**：

- 位置：线性插值
- 旋转：四元数 SLERP
- 缩放：线性插值

这是最高质量的混合方式，避免了矩阵混合的所有问题。

### 2.4 逆运动学（IK）基础

**正向运动学（FK）**：给定关节角度，计算末端位置。

**逆运动学（IK）**：给定末端目标位置，求解关节角度。

**两骨 IK**（手臂/腿部）：

给定上臂长 $l_1$，前臂长 $l_2$，目标距离 $d$：

$$\cos\theta_2 = \frac{d^2 - l_1^2 - l_2^2}{2 l_1 l_2}$$

$$\theta_1 = \text{atan2}(l_2 \sin\theta_2, l_1 + l_2 \cos\theta_2)$$

**FABRIK（Forward And Backward Reaching IK）**：
- 迭代算法，适用于多关节链
- 前向传播：从末端到根，每个关节向目标方向移动
- 后向传播：从根到末端，保持关节距离约束

---

## 3. 工程实践

### 3.1 Panda3D 动画架构

```
Actor（Python 层）
    ↓
Character（C++ 节点）
    ↓
PartBundle（骨骼层次树）
    ├── MovingPartMatrix（骨骼关节）
    │   ├── MovingPartMatrix（子关节）
    │   └── ...
    └── MovingPartScalar（变形目标权重）

AnimBundle（动画数据）
    ├── AnimChannelMatrixXfmTable（关节动画通道）
    │   └── 每帧的 pos/hpr/scale 数据表
    └── AnimChannelScalarTable（标量动画通道）

AnimControl（绑定控制器）
    ├── 引用 PartBundle（骨骼）
    ├── 引用 AnimBundle（动画数据）
    ├── 当前帧号、播放速率
    └── 权重（用于混合）
```

**关键关系**：
- `PartBundle`：骨骼的**结构**（层次、初始姿势）
- `AnimBundle`：动画的**数据**（每帧每关节的变换）
- `AnimControl`：将两者**绑定**，控制播放状态

### 3.2 动画绑定（Binding）

绑定过程将 `AnimBundle` 的通道与 `PartBundle` 的关节一一对应：

```
AnimBundle                    PartBundle
  "Torso" channel    →→→→→    "Torso" joint
  "LeftArm" channel  →→→→→    "LeftArm" joint
  "RightLeg" channel →→→→→    "RightLeg" joint
  "Head" channel     →→→→→    "Head" joint
```

**名称匹配**：通过关节名称字符串匹配，不要求顺序一致。

**部分绑定（PartSubset）**：可以只绑定骨骼的一个子集，用于上半身/下半身分离动画。

### 3.3 动画混合策略

**单动画**（默认）：
```
set_control_effect(walk_anim, 1.0)
→ 只播放 walk_anim
```

**双动画混合**（需要 `set_anim_blend_flag(True)`）：
```
set_control_effect(walk_anim, 0.7)
set_control_effect(run_anim, 0.3)
→ 70% 走路 + 30% 跑步（过渡动画）
```

**上下半身分离**：
```
# 下半身：走路动画
walk_control = actor.get_anim_control("walk")
walk_control.set_control_effect(1.0)

# 上半身：射击动画（只影响上半身关节）
shoot_control = actor.bind_anim("shoot", subset=upper_body_subset)
shoot_control.set_control_effect(1.0)
```

### 3.4 帧插值

**帧插值（Frame Blend）**：在两个关键帧之间线性插值，使动画更平滑：

```
frame_blend_flag = True

当前时间 t = 2.3 帧
→ 在第 2 帧和第 3 帧之间插值，权重 0.7/0.3
→ 结果 = 0.7 * frame[2] + 0.3 * frame[3]
```

**不开启帧插值**：直接取最近的整数帧（可能有跳帧感）。

---

## 4. Panda3D 源码解析

### 4.1 PartBundle 与 AnimBundle

**文件**：[`panda/src/chan/partBundle.h`](../../panda/src/chan/partBundle.h)

```cpp
// partBundle.h:46
class EXPCL_PANDA_CHAN PartBundle : public PartGroup {
PUBLISHED:
  // 混合类型
  enum BlendType {
    BT_linear,              // 矩阵线性混合（快速，有糖果纸问题）
    BT_normalized_linear,   // 归一化线性混合（推荐）
    BT_componentwise,       // 组件式混合（HPR 线性）
    BT_componentwise_quat,  // 组件式混合（旋转用四元数 SLERP）
  };

  // 动画混合控制
  void set_anim_blend_flag(bool anim_blend_flag);  // 允许多动画混合
  void set_frame_blend_flag(bool frame_blend_flag); // 开启帧插值

  // 绑定动画
  PT(AnimControl) bind_anim(AnimBundle *anim,
                            int hierarchy_match_flags = 0,
                            const PartSubset &subset = PartSubset());

  // 关节控制
  bool freeze_joint(std::string_view joint_name,
                    const TransformState *transform);  // 冻结关节
  bool control_joint(std::string_view joint_name,
                     PandaNode *node);  // 用场景图节点控制关节

  // 更新
  bool update();        // 按需更新（有延迟优化）
  bool force_update();  // 强制立即更新

private:
  class CData : public CycleData {
  public:
    BlendType _blend_type;
    bool _anim_blend_flag;
    bool _frame_blend_flag;
    LMatrix4 _root_xform;

    // 当前激活的动画及其权重
    // key: AnimControl*, value: 权重 [0,1]
    ChannelBlend _blend;  // pmap<AnimControl*, PN_stdfloat>

    bool _anim_changed;
    double _last_update;
  };
};
```

### 4.2 AnimControl 时间控制

**文件**：[`panda/src/chan/animControl.h`](../../panda/src/chan/animControl.h)

```cpp
// animControl.h:38
class EXPCL_PANDA_CHAN AnimControl
    : public TypedReferenceCount, public AnimInterface, public Namable {
PUBLISHED:
  // 继承自 AnimInterface 的播放控制
  void play();                    // 播放一次
  void play(double from, double to);  // 播放指定帧范围
  void loop(bool restart);        // 循环播放
  void loop(bool restart, double from, double to);
  void pingpong(bool restart);    // 来回播放
  void stop();                    // 停止

  bool is_playing() const;
  double get_play_rate() const;
  void set_play_rate(double play_rate);  // 播放速率（1.0=正常，2.0=2倍速）

  double get_frame_rate() const;  // 动画帧率（fps）
  int get_num_frames() const;     // 总帧数
  double get_full_frame() const;  // 当前帧（浮点数）
  int get_frame() const;          // 当前帧（整数）

  // 绑定信息
  PartBundle *get_part() const;   // 对应的骨骼
  AnimBundle *get_anim() const;   // 对应的动画数据
  const BitArray &get_bound_joints() const;  // 已绑定的关节位掩码

private:
  int _marked_frame;    // 上次 mark_channels() 时的帧号
  double _marked_frac;  // 上次 mark_channels() 时的帧小数部分
  BitArray _bound_joints;  // 已绑定关节的位掩码
};
```

### 4.3 BlendType 混合类型

```cpp
// partBundle.h:71
enum BlendType {
  // 矩阵线性混合：直接对 4×4 矩阵做加权平均
  // 优点：最快
  // 缺点：旋转混合不正确（糖果纸扭曲）
  BT_linear,

  // 归一化线性混合：分离旋转和缩放，分别混合
  // 优点：避免糖果纸问题，骨骼保持正确大小
  // 缺点：骨骼层次必须完全连接
  BT_normalized_linear,

  // 组件式混合：H、P、R 分别线性插值
  // 优点：直觉上正确
  // 缺点：欧拉角插值可能有万向锁
  BT_componentwise,

  // 组件式四元数混合：位置/缩放线性，旋转用四元数 SLERP
  // 优点：最高质量，无万向锁
  // 缺点：最慢
  BT_componentwise_quat,
};
```

### 4.4 do_update() 更新流程

```cpp
// partBundle.cxx（简化）
bool PartBundle::update() {
  Thread *current_thread = Thread::get_current_thread();
  CDLockedStageReader cdata(_cycler, 0, current_thread);

  double now = ClockObject::get_global_clock()->get_frame_time(current_thread);

  // 检查是否需要更新（有延迟优化）
  if (now > cdata->_last_update + _update_delay || cdata->_anim_changed) {
    bool frame_blend_flag = cdata->_frame_blend_flag;

    // 递归更新所有关节
    bool any_changed = do_update(this, cdata, nullptr, false,
                                 cdata->_anim_changed, current_thread);

    // 标记所有动画通道（记录当前帧号，用于下次比较）
    for (auto &[control, weight] : cdata->_blend) {
      control->mark_channels(frame_blend_flag);
    }

    return any_changed;
  }
  return false;
}

// do_update() 递归遍历骨骼树
// 对每个 MovingPartMatrix（关节）：
//   1. 从所有激活的 AnimControl 中读取当前帧的变换
//   2. 按权重混合（根据 BlendType）
//   3. 更新关节的世界变换矩阵
//   4. 通知 JointVertexTransform 更新蒙皮矩阵
```

---

## 5. 代码演示

### 5.1 Python：Actor 基本动画

```python
from direct.actor.Actor import Actor
from panda3d.core import LPoint3

# ── 加载 Actor ───────────────────────────────────────────────────────────────
# Actor 是 Panda3D 的高层动画接口
actor = Actor(
    "models/panda-model",           # 模型文件
    {
        "walk": "models/panda-walk4",  # 动画文件
        "run": "models/panda-run",
        "idle": "models/panda-idle",
    }
)
actor.reparent_to(render)

# ── 基本播放控制 ─────────────────────────────────────────────────────────────
actor.loop("walk")          # 循环播放走路动画
actor.play("walk")          # 播放一次
actor.stop()                # 停止

# 播放速率
actor.set_play_rate(2.0, "walk")   # 2倍速
actor.set_play_rate(0.5, "walk")   # 半速（慢动作）
actor.set_play_rate(-1.0, "walk")  # 倒放

# 播放指定帧范围
actor.play("walk", fromFrame=10, toFrame=30)
actor.loop("walk", fromFrame=10, toFrame=30)

# 获取当前帧
current_frame = actor.get_current_frame("walk")
total_frames = actor.get_num_frames("walk")
print(f"Frame: {current_frame}/{total_frames}")

# ── 帧插值（更平滑的动画）──────────────────────────────────────────────────
actor.set_blend(frameBlend=True)  # 开启帧插值
```

### 5.2 Python：动画混合

```python
from direct.actor.Actor import Actor

actor = Actor("character", {
    "walk": "walk_anim",
    "run": "run_anim",
    "shoot": "shoot_anim",
})

# ── 开启动画混合 ─────────────────────────────────────────────────────────────
actor.set_blend(animBlend=True, frameBlend=True)

# 设置混合权重（权重之和不必为 1，Panda3D 会自动归一化）
actor.set_control_effect("walk", 0.7)
actor.set_control_effect("run", 0.3)

# 同时播放两个动画
actor.loop("walk")
actor.loop("run")

# ── 平滑过渡（手动插值权重）─────────────────────────────────────────────────
from direct.interval.LerpInterval import LerpFunctionInterval

def transition_to_run(t):
    """从走路过渡到跑步，t 从 0 到 1"""
    actor.set_control_effect("walk", 1.0 - t)
    actor.set_control_effect("run", t)

transition = LerpFunctionInterval(
    transition_to_run,
    duration=0.5,
    fromData=0.0,
    toData=1.0
)
transition.start()

# ── 上下半身分离动画 ─────────────────────────────────────────────────────────
from panda3d.core import PartSubset

# 定义上半身关节子集
upper_body = PartSubset()
upper_body.add_include_joint("Spine")
upper_body.add_include_joint("LeftArm")
upper_body.add_include_joint("RightArm")
upper_body.add_include_joint("Head")

# 绑定射击动画到上半身
shoot_control = actor.bind_anim("shoot", subset=upper_body)

# 下半身播放走路，上半身播放射击
actor.loop("walk")
shoot_control.loop(True)
```

### 5.3 Python：关节控制

```python
from direct.actor.Actor import Actor
from panda3d.core import NodePath, LPoint3

actor = Actor("character", {"walk": "walk_anim"})
actor.reparent_to(render)

# ── 暴露关节（获取关节的 NodePath）──────────────────────────────────────────
# expose_joint() 返回一个跟随关节运动的 NodePath
right_hand = actor.expose_joint(None, "modelRoot", "RightHand")

# 将武器附加到手部关节
weapon = loader.load_model("sword.egg")
weapon.reparent_to(right_hand)
# 武器会自动跟随手部关节运动

# ── 控制关节（用 NodePath 驱动关节）─────────────────────────────────────────
# control_joint() 让场景图节点控制关节（用于 IK 等）
head_control = actor.control_joint(None, "modelRoot", "Head")

# 现在可以通过 head_control 控制头部朝向
def look_at_target(task):
    target_pos = some_target.get_pos(actor)
    head_control.look_at(target_pos)
    return task.cont

base.task_mgr.add(look_at_target, "look_at_target")

# ── 冻结关节 ─────────────────────────────────────────────────────────────────
# freeze_joint() 将关节固定在指定变换
from panda3d.core import TransformState, LVecBase3

# 冻结左臂（如受伤状态）
actor.get_part("modelRoot").freeze_joint(
    "LeftArm",
    TransformState.make_hpr(LVecBase3(0, -90, 0))  # 下垂姿势
)

# 释放冻结
actor.get_part("modelRoot").release_joint("LeftArm")
```

### 5.4 Python：动画状态机

```python
from direct.fsm.FSM import FSM
from direct.actor.Actor import Actor

class CharacterFSM(FSM):
    def __init__(self, actor):
        FSM.__init__(self, "CharacterFSM")
        self.actor = actor
        self.actor.set_blend(animBlend=True, frameBlend=True)

    def enterIdle(self):
        self.actor.loop("idle")

    def exitIdle(self):
        self.actor.stop("idle")

    def enterWalk(self):
        self.actor.loop("walk")

    def exitWalk(self):
        self.actor.stop("walk")

    def enterRun(self):
        self.actor.loop("run")

    def exitRun(self):
        self.actor.stop("run")

    def enterJump(self):
        self.actor.play("jump")
        # 跳跃动画结束后自动回到 Idle
        duration = self.actor.get_duration("jump")
        base.task_mgr.do_method_later(duration, self._jump_done, "jump_done")

    def _jump_done(self, task):
        self.request("Idle")
        return task.done

    def exitJump(self):
        base.task_mgr.remove("jump_done")

# 使用状态机
actor = Actor("character", {
    "idle": "idle_anim",
    "walk": "walk_anim",
    "run": "run_anim",
    "jump": "jump_anim",
})
fsm = CharacterFSM(actor)
fsm.request("Idle")

# 状态转换
fsm.request("Walk")   # 开始走路
fsm.request("Run")    # 开始跑步
fsm.request("Jump")   # 跳跃（自动返回 Idle）
```

### 5.5 Python：程序化动画（IK 示例）

```python
from panda3d.core import NodePath, LPoint3, LVector3
import math

class TwoBoneIK:
    """简单的两骨 IK（用于腿部）"""

    def __init__(self, actor, upper_joint, lower_joint, end_joint):
        self.upper = actor.control_joint(None, "modelRoot", upper_joint)
        self.lower = actor.control_joint(None, "modelRoot", lower_joint)
        self.end = actor.expose_joint(None, "modelRoot", end_joint)

        # 获取骨骼长度
        self.l1 = (self.lower.get_pos(self.upper)).length()
        self.l2 = (self.end.get_pos(self.lower)).length()

    def solve(self, target_pos):
        """求解 IK，使末端到达 target_pos"""
        # 计算到目标的距离
        root_pos = self.upper.get_pos(render)
        d = (target_pos - root_pos).length()
        d = min(d, self.l1 + self.l2 - 0.001)  # 限制在可达范围内

        # 两骨 IK 公式
        cos_angle2 = (d*d - self.l1*self.l1 - self.l2*self.l2) / (2 * self.l1 * self.l2)
        cos_angle2 = max(-1, min(1, cos_angle2))  # 夹紧到 [-1, 1]
        angle2 = math.acos(cos_angle2)

        cos_angle1 = (self.l1*self.l1 + d*d - self.l2*self.l2) / (2 * self.l1 * d)
        cos_angle1 = max(-1, min(1, cos_angle1))
        angle1 = math.acos(cos_angle1)

        # 应用关节角度
        direction = (target_pos - root_pos).normalized()
        self.upper.look_at(root_pos + direction)
        self.upper.set_p(self.upper, math.degrees(angle1))
        self.lower.set_p(self.lower, math.degrees(angle2) - 180)

# 使用 IK
actor = Actor("character", {"walk": "walk_anim"})
left_leg_ik = TwoBoneIK(actor, "LeftThigh", "LeftShin", "LeftFoot")

def update_ik(task):
    # 射线检测地面
    ground_pos = get_ground_position(actor.get_pos() + LVector3(0, 0, -1))
    left_leg_ik.solve(ground_pos)
    return task.cont

base.task_mgr.add(update_ik, "update_ik")
```

---

## 6. 性能分析

### 6.1 动画更新代价

| 操作 | 代价 | 说明 |
|------|------|------|
| 单动画更新 | O(N_joints) | N_joints 个矩阵计算 |
| 双动画混合 | O(2 × N_joints) | 两套矩阵 + 混合 |
| 帧插值 | +O(N_joints) | 额外的插值计算 |
| 蒙皮（CPU） | O(N_verts × N_influences) | 每顶点多骨骼加权 |
| 蒙皮（GPU） | O(N_verts) 并行 | GPU 顶点着色器 |

### 6.2 混合类型性能对比

| BlendType | 速度 | 质量 | 推荐场景 |
|-----------|------|------|---------|
| BT_linear | 最快 | 低（糖果纸） | 背景角色 |
| BT_normalized_linear | 快 | 中 | 一般角色 |
| BT_componentwise | 中 | 中 | 需要精确 HPR 控制 |
| BT_componentwise_quat | 慢 | 最高 | 主角、过场动画 |

### 6.3 常见性能陷阱

```python
# ❌ 错误：每帧重新绑定动画
def update(task):
    actor.bind_anim("walk")  # 每帧绑定！代价极高
    actor.loop("walk")
    return task.cont

# ✅ 正确：只绑定一次，之后只控制播放
actor.load_anims({"walk": "walk_anim"})  # 预加载
actor.loop("walk")  # 直接播放

# ❌ 错误：不必要的 expose_joint（每个都创建额外节点）
for joint_name in all_joint_names:
    actor.expose_joint(None, "modelRoot", joint_name)  # 100 个关节！

# ✅ 正确：只暴露需要的关节
right_hand = actor.expose_joint(None, "modelRoot", "RightHand")
left_hand = actor.expose_joint(None, "modelRoot", "LeftHand")

# ❌ 错误：CPU 蒙皮（大量顶点时极慢）
# 默认情况下 Panda3D 使用 GPU 蒙皮（顶点着色器）
# 不要强制使用 CPU 蒙皮

# ✅ 正确：确保使用 GPU 蒙皮
# 在 config.prc 中：
# hardware-animated-vertices 1  （默认已开启）

# ❌ 错误：过多骨骼影响（每顶点 8 个骨骼）
# 标准：每顶点最多 4 个骨骼影响
# 超过 4 个会显著增加 GPU 蒙皮代价

# ✅ 正确：限制每顶点骨骼影响数
# 在建模软件中设置最大权重数为 4
```

### 6.4 动画 LOD

```python
# 根据距离降低动画更新频率
class AnimLOD:
    def __init__(self, actor, camera):
        self.actor = actor
        self.camera = camera

    def update(self, task):
        dist = (self.actor.get_pos() - self.camera.get_pos()).length()

        if dist < 20:
            # 近距离：全帧率更新，帧插值
            self.actor.set_blend(frameBlend=True)
            update_rate = 1.0
        elif dist < 50:
            # 中距离：半帧率
            self.actor.set_blend(frameBlend=False)
            update_rate = 0.5
        else:
            # 远距离：1/4 帧率，无插值
            self.actor.set_blend(frameBlend=False)
            update_rate = 0.25

        # 通过 set_play_rate 控制更新频率
        self.actor.set_play_rate(update_rate, "walk")
        return task.cont
```

---

## 小结

| 概念 | 核心思想 | Panda3D 实现 |
|------|----------|-------------|
| 骨骼动画 | 骨骼层次 + 蒙皮权重 | `PartBundle` + `Character` |
| 关键帧插值 | LERP/SLERP 在帧间插值 | `frame_blend_flag` |
| 动画混合 | 多动画加权平均 | `set_control_effect()` |
| BlendType | 矩阵/组件/四元数混合 | `set_blend_type()` |
| 关节控制 | 场景图节点驱动关节 | `control_joint()` |
| 关节暴露 | 关节驱动场景图节点 | `expose_joint()` |
| 动画状态机 | FSM 管理动画状态 | `direct.fsm.FSM` |

**核心设计哲学**：
1. **数据驱动**：`AnimBundle` 存储纯数据，`PartBundle` 存储结构，`AnimControl` 管理状态
2. **延迟更新**：`update_delay` 避免每帧都重算骨骼变换
3. **GPU 蒙皮**：骨骼矩阵上传 GPU，顶点变换在着色器中并行计算
4. **灵活混合**：支持多动画混合、部分骨骼绑定、关节手动控制