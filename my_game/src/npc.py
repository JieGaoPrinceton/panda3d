"""
src/npc.py — NPC / AI 巡逻系统
================================
演示 Panda3D 的 Task + 路径点 AI：
- NPC 模型加载 + 巡逻路径
- 状态：巡逻 → 发现玩家 → 追逐 → 返回
- 视野范围检测

引擎对应: direct.task · direct.fsm.FSM · Actor
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, List, Optional, Tuple

from panda3d.core import Vec3, Point3, NodePath, PandaNode
from direct.actor.Actor import Actor

from .constants import MODEL_BASE

if TYPE_CHECKING:
    from direct.showbase.ShowBase import ShowBase
    from .player import PlayerController


class NPC:
    """单个 NPC 实体。"""

    # NPC 状态
    STATE_PATROL = "patrol"
    STATE_CHASE = "chase"
    STATE_RETURN = "return"
    STATE_IDLE = "idle"

    def __init__(self, base: ShowBase, name: str,
                 patrol_points: List[Tuple[float, float, float]],
                 speed: float = 3.0,
                 detect_range: float = 12.0,
                 lose_range: float = 18.0) -> None:
        self._base = base
        self.name = name
        self.speed = speed
        self.detect_range = detect_range
        self.lose_range = lose_range
        self._dialogue_triggered = False  # 本次追逐是否已触发对话

        # 巡逻路径
        self._patrol_points = [Vec3(*p) for p in patrol_points]
        self._current_waypoint = 0

        # 状态
        self.state = self.STATE_PATROL

        # 创建 NPC 模型（复用 panda 模型，缩放不同以区分）
        try:
            self.model = Actor(
                f"{MODEL_BASE}/panda-model",
                {"walk": f"{MODEL_BASE}/panda-walk4"},
            )
            self.model.loop("walk")
        except Exception:
            self.model = NodePath(PandaNode(name))

        self.model.setScale(0.003)  # 比玩家小一点
        self.model.reparentTo(base.render)

        # 设置初始位置
        if self._patrol_points:
            start = self._patrol_points[0]
            self.model.setPos(start.getX(), start.getY(), start.getZ())

        # NPC 颜色（区分于玩家）
        self.model.setColorScale(0.5, 0.8, 1.0, 1.0)

    def update(self, dt: float, player_pos: Point3) -> Optional[str]:
        """每帧更新 NPC 行为。

        Returns
        -------
        str | None
            当 NPC 首次进入追逐状态时返回 NPC 名称（用于触发对话），
            否则返回 ``None``。
        """
        npc_pos = self.model.getPos()
        dist_to_player = (npc_pos - player_pos).length()
        triggered_name: Optional[str] = None

        if self.state == self.STATE_PATROL:
            self._do_patrol(dt)
            # 检测玩家
            if dist_to_player < self.detect_range:
                self.state = self.STATE_CHASE
                if not self._dialogue_triggered:
                    self._dialogue_triggered = True
                    triggered_name = self.name

        elif self.state == self.STATE_CHASE:
            self._do_chase(dt, player_pos)
            # 丢失玩家
            if dist_to_player > self.lose_range:
                self.state = self.STATE_RETURN
                self._dialogue_triggered = False  # 重置，下次再遇可再触发

        elif self.state == self.STATE_RETURN:
            self._do_return(dt)
            # 检测玩家
            if dist_to_player < self.detect_range:
                self.state = self.STATE_CHASE
                if not self._dialogue_triggered:
                    self._dialogue_triggered = True
                    triggered_name = self.name

        elif self.state == self.STATE_IDLE:
            pass

        return triggered_name

    def _do_patrol(self, dt: float) -> None:
        """巡逻行为：沿路径点移动。"""
        if not self._patrol_points:
            return

        target = self._patrol_points[self._current_waypoint]
        self._move_toward(target, dt)

        # 到达路径点，切换到下一个
        npc_pos = self.model.getPos()
        dist = (Vec3(npc_pos.getX(), npc_pos.getY(), 0) -
                Vec3(target.getX(), target.getY(), 0)).length()
        if dist < 1.0:
            self._current_waypoint = (
                (self._current_waypoint + 1) % len(self._patrol_points)
            )

    def _do_chase(self, dt: float, player_pos: Point3) -> None:
        """追逐行为：朝玩家移动。"""
        target = Vec3(player_pos.getX(), player_pos.getY(),
                      self.model.getZ())
        self._move_toward(target, dt, speed_mult=1.3)

    def _do_return(self, dt: float) -> None:
        """返回行为：回到最近的巡逻点。"""
        if not self._patrol_points:
            self.state = self.STATE_IDLE
            return

        target = self._patrol_points[self._current_waypoint]
        self._move_toward(target, dt, speed_mult=0.8)

        npc_pos = self.model.getPos()
        dist = (Vec3(npc_pos.getX(), npc_pos.getY(), 0) -
                Vec3(target.getX(), target.getY(), 0)).length()
        if dist < 1.0:
            self.state = self.STATE_PATROL

    def _move_toward(self, target: Vec3, dt: float,
                     speed_mult: float = 1.0) -> None:
        """朝目标位置移动并面向目标。"""
        npc_pos = self.model.getPos()
        direction = Vec3(
            target.getX() - npc_pos.getX(),
            target.getY() - npc_pos.getY(),
            0,
        )
        dist = direction.length()
        if dist < 0.1:
            return

        direction.normalize()
        move = direction * self.speed * speed_mult * dt
        new_pos = npc_pos + move
        new_pos.setZ(npc_pos.getZ())  # 保持高度
        self.model.setPos(new_pos)

        # 面向移动方向
        angle = math.degrees(math.atan2(-direction.getX(), direction.getY()))
        self.model.setH(angle)

    def cleanup(self) -> None:
        """清理 NPC。"""
        if self.model and not self.model.isEmpty():
            self.model.removeNode()


class NPCManager:
    """NPC 管理器。"""

    def __init__(self, base: ShowBase) -> None:
        self._base = base
        self._npcs: List[NPC] = []
        self._enabled = True

    def spawn_npc(self, name: str,
                  patrol_points: List[Tuple[float, float, float]],
                  **kwargs) -> NPC:
        """
        生成一个 NPC。

        Parameters
        ----------
        name : str
            NPC 名称。
        patrol_points : list
            巡逻路径点列表 [(x, y, z), ...]。
        """
        npc = NPC(self._base, name, patrol_points, **kwargs)
        self._npcs.append(npc)
        return npc

    def spawn_default_npcs(self) -> None:
        """生成默认的 NPC 集合。"""
        # NPC 1: 在场景左侧巡逻
        self.spawn_npc("guard_1", [
            (-10, 10, -0.5),
            (-10, 30, -0.5),
            (-5, 30, -0.5),
            (-5, 10, -0.5),
        ], speed=2.5, detect_range=10.0)

        # NPC 2: 在场景右侧巡逻
        self.spawn_npc("guard_2", [
            (8, 15, -0.5),
            (12, 25, -0.5),
            (8, 35, -0.5),
            (4, 25, -0.5),
        ], speed=3.0, detect_range=8.0)

    def update(self, dt: float, player_pos: Point3) -> Optional[str]:
        """每帧更新所有 NPC。

        Returns
        -------
        str | None
            如果有 NPC 触发了对话，返回该 NPC 名称；否则返回 ``None``。
        """
        if not self._enabled:
            return None
        for npc in self._npcs:
            triggered = npc.update(dt, player_pos)
            if triggered is not None:
                return triggered
        return None

    def toggle(self) -> bool:
        """切换 NPC 系统开关。"""
        self._enabled = not self._enabled
        for npc in self._npcs:
            if self._enabled:
                npc.model.show()
            else:
                npc.model.hide()
        return self._enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def npc_count(self) -> int:
        return len(self._npcs)

    def get_npc_states(self) -> List[dict]:
        """获取所有 NPC 状态（用于 HUD 显示）。"""
        return [
            {"name": npc.name, "state": npc.state}
            for npc in self._npcs
        ]

    def cleanup(self) -> None:
        """清理所有 NPC。"""
        for npc in self._npcs:
            npc.cleanup()
        self._npcs.clear()
