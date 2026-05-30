"""
src/picking.py — 鼠标拾取交互（选中 + 高亮 + 删除）
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from panda3d.core import NodePath, Point3
from panda3d.bullet import BulletRigidBodyNode

if TYPE_CHECKING:
    from direct.showbase.ShowBase import ShowBase
    from .physics import PhysicsManager
    from .audio import AudioManager


class PickingManager:
    """鼠标射线拾取 + 选中高亮 + 删除。"""

    def __init__(self, base: ShowBase, physics: PhysicsManager, audio: AudioManager) -> None:
        self._base = base
        self._physics = physics
        self._audio = audio

        self._selected_np: Optional[NodePath] = None
        self._selected_original_color = None

    def on_pick(self) -> None:
        """鼠标左键点击：射线拾取场景中的物理方块。"""
        if not self._base.mouseWatcherNode.hasMouse():
            return

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

            if hit_name.startswith("box_"):
                hit_np = self._base.render.find(f"**/{hit_name}")
                if not hit_np.isEmpty():
                    self._select_object(hit_np)
                    return

        self.deselect()

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
