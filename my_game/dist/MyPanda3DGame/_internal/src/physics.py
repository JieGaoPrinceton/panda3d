"""
src/physics.py — Bullet 物理引擎管理
======================================
职责:
    - 创建 BulletWorld（重力、步进）
    - 创建地面碰撞平面
    - 动态方块的生成与销毁
    - 物理调试渲染（线框显示碰撞体）

引擎对应: panda3d.bullet.BulletWorld
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
    """Bullet 物理世界管理器。

    Attributes
    ----------
    world : BulletWorld
        物理世界实例。
    box_count : int
        当前场景中动态方块数量。
    spawned_boxes : list[NodePath]
        所有已生成的动态方块节点列表。
    """

    def __init__(self, base: ShowBase) -> None:
        self._base = base

        # ── 创建物理世界 ──
        self.world = BulletWorld()
        self.world.setGravity(Vec3(0, 0, DEFAULTS["gravity"]))

        # ── 调试渲染（F1 可切换显示） ──
        debug_node = BulletDebugNode("bullet_debug")
        debug_node.showWireframe(True)       # 显示碰撞体线框
        debug_node.showConstraints(True)     # 显示约束
        debug_node.showBoundingBoxes(False)  # 不显示 AABB
        debug_node.showNormals(False)        # 不显示法线
        self.debug_np = base.render.attachNewNode(debug_node)
        self.debug_np.hide()
        self.world.setDebugNode(debug_node)

        self.debug_visible = False
        self.box_count = 0
        self.spawned_boxes: List[NodePath] = []

        # ── 运行时可调物理参数 ──
        self.gravity = DEFAULTS["gravity"]
        self.box_mass = DEFAULTS["box_mass"]
        self.box_friction = DEFAULTS["box_friction"]
        self.box_restitution = DEFAULTS["box_restitution"]
        self.ground_friction = DEFAULTS["ground_friction"]
        self.ground_restitution = DEFAULTS["ground_restitution"]

        # ── 创建地面碰撞平面 ──
        self._ground_np = self._create_ground_plane()

    @property
    def ground_np(self) -> NodePath:
        """地面物理体节点。"""
        return self._ground_np

    # ──────────────────────────────────────────────────────────
    # 地面
    # ──────────────────────────────────────────────────────────

    def _create_ground_plane(self) -> NodePath:
        """创建无限大地面碰撞平面（Z=0 向上）。

        使用 BulletPlaneShape(法线, 偏移) 创建，质量=0 表示静态物体。
        """
        shape = BulletPlaneShape(Vec3(0, 0, 1), 0)  # 法线朝上
        body = BulletRigidBodyNode("ground_physics")
        body.addShape(shape)
        body.setMass(0)  # 静态物体
        body.setFriction(self.ground_friction)
        body.setRestitution(self.ground_restitution)
        np = self._base.render.attachNewNode(body)
        np.setPos(0, 0, -1)  # 地面位于 Z=-1
        self.world.attachRigidBody(body)
        return np

    # ──────────────────────────────────────────────────────────
    # 动态方块
    # ──────────────────────────────────────────────────────────

    def spawn_box(self, spawn_pos: Vec3) -> NodePath:
        """在指定位置生成一个动态物理方块。

        Parameters
        ----------
        spawn_pos : Vec3
            生成位置。

        Returns
        -------
        NodePath
            新方块的场景节点。
        """
        self.box_count += 1
        size = 0.5  # 半边长

        # 物理体
        shape = BulletBoxShape(Vec3(size, size, size))
        body = BulletRigidBodyNode(f"box_{self.box_count}")
        body.setMass(self.box_mass)
        body.addShape(shape)
        body.setFriction(self.box_friction)
        body.setRestitution(self.box_restitution)

        box_np = self._base.render.attachNewNode(body)
        box_np.setPos(spawn_pos)
        self.world.attachRigidBody(body)

        # 加载可视模型
        try:
            box_model = self._base.loader.loadModel(f"{MODEL_BASE}/box")
            box_model.setScale(size * 2)  # 模型缩放到物理体大小
            box_model.reparentTo(box_np)
        except Exception:
            pass

        # 随机颜色
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

    # ──────────────────────────────────────────────────────────
    # 物理步进
    # ──────────────────────────────────────────────────────────

    def step(self, dt: float) -> None:
        """推进物理模拟一帧。

        Parameters
        ----------
        dt : float
            帧间隔时间（秒）。
            内部使用 10 个子步骤，每步 1/180 秒，确保稳定性。
        """
        self.world.doPhysics(dt, 10, 1.0 / 180.0)

    # ──────────────────────────────────────────────────────────
    # 调试渲染
    # ──────────────────────────────────────────────────────────

    def toggle_debug(self) -> None:
        """切换物理调试线框显示。"""
        self.debug_visible = not self.debug_visible
        if self.debug_visible:
            self.debug_np.show()
        else:
            self.debug_np.hide()
