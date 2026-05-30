"""
src/picking.py — 鼠标拾取交互（选中 + 高亮 + 删除 + 经验方块拾取）
"""

from __future__ import annotations

from typing import Optional, Callable, TYPE_CHECKING

from panda3d.core import NodePath, Point3
from panda3d.bullet import BulletRigidBodyNode

if TYPE_CHECKING:
    from direct.showbase.ShowBase import ShowBase
    from .physics import PhysicsManager
    from .audio import AudioManager


class PickingManager:
    """鼠标射线拾取 + 选中高亮 + 删除 + 经验方块点击拾取。"""

    def __init__(self, base: ShowBase, physics: PhysicsManager, audio: AudioManager) -> None:
        self._base = base
        self._physics = physics
        self._audio = audio

        self._selected_np: Optional[NodePath] = None
        self._selected_original_color = None

        # 经验方块点击拾取回调：(node_name) -> Optional[int]
        self._gem_collect_callback: Optional[Callable[[str], Optional[int]]] = None

    def set_gem_collect_callback(self, callback: Callable[[str], Optional[int]]) -> None:
        """设置经验方块拾取回调函数。"""
        self._gem_collect_callback = callback

    def on_pick(self) -> Optional[int]:
        """鼠标左键点击：射线拾取场景中的物理方块。

        如果点击到经验方块，返回获得的经验值；否则返回 None。
        """
        if not self._base.mouseWatcherNode.hasMouse():
            return None

        mpos = self._base.mouseWatcherNode.getMouse()

        from_pos = Point3()
        to_pos = Point3()
        self._base.camLens.extrude(mpos, from_pos, to_pos)

        from_world = self._base.render.getRelativePoint(self._base.camera, from_pos)
        to_world = self._base.render.getRelativePoint(self._base.camera, to_pos)

        result = self._physics.world.rayTestClosest(from_world, to_world)

        if result.hasHit():
            hit_node = result.getNode()
            hit_name = hit_node.getName()

            # 经验方块 — 点击直接拾取
            if hit_name.startswith("gem_") and self._gem_collect_callback:
                exp = self._gem_collect_callback(hit_name)
                if exp is not None:
                    self._audio.play("pick")
                    return exp

            # 普通方块 — 选中高亮
            if hit_name.startswith("box_"):
                hit_np = self._base.render.find(f"**/{hit_name}")
                if not hit_np.isEmpty():
                    self._select_object(hit_np)
                    return None

        self.deselect()
        return None

    def _select_object(self, np: NodePath) -> None:
        """选中一个物体：高亮显示。"""
        self.deselect()
        self._selected_np = np
        self._selected_original_color = np.getColor()
        np.setColor(1.0, 1.0, 0.2, 1.0)
        self._audio.play("pick")

    def deselect(self) -> None:
        """取消选中。"""
        if self._selected_np and not self._selected_np.isEmpty():
            self._selected_np.setColor(self._selected_original_color)
        self._selected_np = None
        self._selected_original_color = None

    def delete_selected(self) -> None:
        """删除选中的方块。"""
        if not self._selected_np or self._selected_np.isEmpty():
            return

        np = self._selected_np
        self._physics.remove_box(np)
        self._selected_np = None
        self._selected_original_color = None
        self._audio.play("delete")
