"""
src/collision.py — Panda3D 原生碰撞检测系统
=============================================
演示 Panda3D 的原生碰撞系统（与 Bullet 物理并存）：
- CollisionTraverser + CollisionHandlerEvent
- 触发区域（进入/离开事件）
- 碰撞可视化

引擎对应: samples/ball-in-maze/ · panda3d.core.Collision*
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Dict, List, Optional

from panda3d.core import (
    CollisionTraverser, CollisionNode,
    CollisionHandlerEvent, CollisionHandlerQueue,
    CollisionSphere, CollisionBox, CollisionRay,
    CollideMask, BitMask32,
    NodePath, Point3, Vec3,
)

if TYPE_CHECKING:
    from direct.showbase.ShowBase import ShowBase


class TriggerZone:
    """触发区域数据。"""

    def __init__(self, name: str, np: NodePath,
                 on_enter: Optional[Callable] = None,
                 on_exit: Optional[Callable] = None) -> None:
        self.name = name
        self.np = np
        self.on_enter = on_enter
        self.on_exit = on_exit


class CollisionManager:
    """
    Panda3D 原生碰撞系统管理器。

    与 Bullet 物理系统并存，用于：
    - 触发区域检测（进入/离开事件）
    - 碰撞事件回调
    - 碰撞可视化调试
    """

    def __init__(self, base: ShowBase) -> None:
        self._base = base
        self._enabled = True
        self._debug_visible = False

        # 碰撞遍历器
        self._traverser = CollisionTraverser("main_traverser")

        # 事件处理器（用于触发区域）
        self._event_handler = CollisionHandlerEvent()
        self._event_handler.addInPattern("into-%in")
        self._event_handler.addOutPattern("outof-%in")

        # 触发区域注册表
        self._triggers: Dict[str, TriggerZone] = {}

        # 玩家碰撞节点
        self._player_collider: Optional[NodePath] = None

    def setup_player_collider(self, player_np: NodePath,
                              radius: float = 1.0) -> None:
        """
        为玩家创建碰撞球体。

        Parameters
        ----------
        player_np : NodePath
            玩家的 NodePath。
        radius : float
            碰撞球半径。
        """
        cnode = CollisionNode("player_collider")
        cnode.addSolid(CollisionSphere(0, 0, 0, radius))
        cnode.setFromCollideMask(BitMask32.bit(1))  # 玩家是 "from" 对象
        cnode.setIntoCollideMask(BitMask32.allOff())  # 玩家不是 "into" 对象

        self._player_collider = player_np.attachNewNode(cnode)
        self._traverser.addCollider(
            self._player_collider, self._event_handler
        )

    def add_trigger_sphere(self, name: str, pos: Point3,
                           radius: float = 3.0,
                           on_enter: Optional[Callable] = None,
                           on_exit: Optional[Callable] = None) -> NodePath:
        """
        添加球形触发区域。

        Parameters
        ----------
        name : str
            触发区域名称。
        pos : Point3
            位置。
        radius : float
            半径。
        on_enter : callable, optional
            进入回调。
        on_exit : callable, optional
            离开回调。
        """
        cnode = CollisionNode(name)
        cnode.addSolid(CollisionSphere(0, 0, 0, radius))
        cnode.setFromCollideMask(BitMask32.allOff())
        cnode.setIntoCollideMask(BitMask32.bit(1))

        trigger_np = self._base.render.attachNewNode(cnode)
        trigger_np.setPos(pos)

        # 注册触发区域
        trigger = TriggerZone(name, trigger_np, on_enter, on_exit)
        self._triggers[name] = trigger

        # 注册事件回调
        if on_enter:
            self._base.accept(f"into-{name}", self._on_trigger_enter)
        if on_exit:
            self._base.accept(f"outof-{name}", self._on_trigger_exit)

        return trigger_np

    def add_trigger_box(self, name: str, pos: Point3,
                        size: Vec3 = Vec3(2, 2, 2),
                        on_enter: Optional[Callable] = None,
                        on_exit: Optional[Callable] = None) -> NodePath:
        """
        添加方形触发区域。

        Parameters
        ----------
        name : str
            触发区域名称。
        pos : Point3
            位置。
        size : Vec3
            半尺寸。
        on_enter : callable, optional
            进入回调。
        on_exit : callable, optional
            离开回调。
        """
        cnode = CollisionNode(name)
        cnode.addSolid(CollisionBox(Point3(0, 0, 0), size.getX(),
                                     size.getY(), size.getZ()))
        cnode.setFromCollideMask(BitMask32.allOff())
        cnode.setIntoCollideMask(BitMask32.bit(1))

        trigger_np = self._base.render.attachNewNode(cnode)
        trigger_np.setPos(pos)

        trigger = TriggerZone(name, trigger_np, on_enter, on_exit)
        self._triggers[name] = trigger

        if on_enter:
            self._base.accept(f"into-{name}", self._on_trigger_enter)
        if on_exit:
            self._base.accept(f"outof-{name}", self._on_trigger_exit)

        return trigger_np

    def _on_trigger_enter(self, entry) -> None:
        """碰撞进入回调。"""
        into_name = entry.getIntoNodePath().getName()
        if into_name in self._triggers:
            trigger = self._triggers[into_name]
            if trigger.on_enter:
                trigger.on_enter(into_name)

    def _on_trigger_exit(self, entry) -> None:
        """碰撞离开回调。"""
        into_name = entry.getIntoNodePath().getName()
        if into_name in self._triggers:
            trigger = self._triggers[into_name]
            if trigger.on_exit:
                trigger.on_exit(into_name)

    def create_demo_triggers(self) -> None:
        """创建演示用的触发区域。"""
        # 加速区域
        self.add_trigger_sphere(
            "speed_zone", Point3(0, 20, 0), radius=5.0,
            on_enter=lambda name: print(f"[Trigger] 进入加速区域: {name}"),
            on_exit=lambda name: print(f"[Trigger] 离开加速区域: {name}"),
        )

        # 危险区域
        self.add_trigger_box(
            "danger_zone", Point3(10, 30, 0), size=Vec3(3, 3, 3),
            on_enter=lambda name: print(f"[Trigger] ⚠ 进入危险区域: {name}"),
            on_exit=lambda name: print(f"[Trigger] 离开危险区域: {name}"),
        )

    def update(self) -> None:
        """每帧执行碰撞检测。"""
        if self._enabled:
            self._traverser.traverse(self._base.render)

    def toggle_debug(self) -> bool:
        """切换碰撞可视化。"""
        self._debug_visible = not self._debug_visible
        if self._debug_visible:
            self._traverser.showCollisions(self._base.render)
            # 显示所有触发区域
            for trigger in self._triggers.values():
                trigger.np.show()
        else:
            self._traverser.hideCollisions()
            for trigger in self._triggers.values():
                trigger.np.show()  # 碰撞节点默认不可见
        return self._debug_visible

    def toggle(self) -> bool:
        """切换碰撞系统开关。"""
        self._enabled = not self._enabled
        return self._enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    def remove_trigger(self, name: str) -> None:
        """移除触发区域。"""
        if name in self._triggers:
            trigger = self._triggers.pop(name)
            if not trigger.np.isEmpty():
                trigger.np.removeNode()
            self._base.ignore(f"into-{name}")
            self._base.ignore(f"outof-{name}")

    def cleanup(self) -> None:
        """清理所有碰撞资源。"""
        for name in list(self._triggers.keys()):
            self.remove_trigger(name)
        if self._player_collider and not self._player_collider.isEmpty():
            self._player_collider.removeNode()
