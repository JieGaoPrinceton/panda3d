"""
src/physics.py — Bullet 物理引擎管理
"""

from __future__ import annotations

import random
from typing import List, TYPE_CHECKING

from panda3d.core import Vec3, NodePath
from panda3d.bullet import (
    BulletWorld,
    BulletPlaneShape,
    BulletBoxShape,
    BulletRigidBodyNode,
    BulletDebugNode,
)

from .constants import MODEL_BASE, DEFAULTS

if TYPE_CHECKING:
    from direct.showbase.ShowBase import ShowBase


class PhysicsManager:
    """Bullet 物理世界管理器。"""

    def __init__(self, base: ShowBase) -> None:
        self._base = base
        self.world = BulletWorld()
        self.world.setGravity(Vec3(0, 0, DEFAULTS["gravity"]))

        # 调试渲染
        debug_node = BulletDebugNode("bullet_debug")
        debug_node.showWireframe(True)
        debug_node.showConstraints(True)
        debug_node.showBoundingBoxes(False)
        debug_node.showNormals(False)
        self.debug_np = base.render.attachNewNode(debug_node)
        self.debug_np.hide()
        self.world.setDebugNode(debug_node)

        self.debug_visible = False
        self.box_count = 0
        self.spawned_boxes: List[NodePath] = []

        # 物理参数（可运行时修改）
        self.gravity = DEFAULTS["gravity"]
        self.box_mass = DEFAULTS["box_mass"]
        self.box_friction = DEFAULTS["box_friction"]
        self.box_restitution = DEFAULTS["box_restitution"]
        self.ground_friction = DEFAULTS["ground_friction"]
        self.ground_restitution = DEFAULTS["ground_restitution"]

        # 创建地面
        self._ground_np = self._create_ground_plane()

    @property
    def ground_np(self) -> NodePath:
        return self._ground_np

    def _create_ground_plane(self) -> NodePath:
        shape = BulletPlaneShape(Vec3(0, 0, 1), 0)
        body = BulletRigidBodyNode("ground_physics")
        body.addShape(shape)
        body.setMass(0)
        body.setFriction(self.ground_friction)
        body.setRestitution(self.ground_restitution)
        np = self._base.render.attachNewNode(body)
        np.setPos(0, 0, -1)
        self.world.attachRigidBody(body)
        return np

    def spawn_box(self, spawn_pos: Vec3) -> NodePath:
        """在指定位置生成一个动态方块。"""
        self.box_count += 1
        size = 0.5

        shape = BulletBoxShape(Vec3(size, size, size))
        body = BulletRigidBodyNode(f"box_{self.box_count}")
        body.setMass(self.box_mass)
        body.addShape(shape)
        body.setFriction(self.box_friction)
        body.setRestitution(self.box_restitution)

        box_np = self._base.render.attachNewNode(body)
        box_np.setPos(spawn_pos)
        self.world.attachRigidBody(body)

        try:
            box_model = self._base.loader.loadModel(f"{MODEL_BASE}/box")
            box_model.setScale(size * 2)
            box_model.reparentTo(box_np)
        except Exception:
            pass

        r, g, b = random.random(), random.random(), random.random()
        box_np.setColor(r, g, b, 1)
        self.spawned_boxes.append(box_np)
        return box_np

    def remove_box(self, np: NodePath) -> None:
        """从物理世界和场景中移除方块。"""
        body = np.node()
        if isinstance(body, BulletRigidBodyNode):
            self.world.removeRigidBody(body)
        if np in self.spawned_boxes:
            self.spawned_boxes.remove(np)
            self.box_count -= 1
        np.removeNode()

    def step(self, dt: float) -> None:
        """推进物理模拟。"""
        self.world.doPhysics(dt, 10, 1.0 / 180.0)

    def toggle_debug(self) -> None:
        self.debug_visible = not self.debug_visible
        if self.debug_visible:
            self.debug_np.show()
        else:
            self.debug_np.hide()
