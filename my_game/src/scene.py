"""
src/scene.py — 场景加载（地面模型 + 障碍物 + 光照）
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from panda3d.core import (
    AmbientLight, DirectionalLight,
    Vec3, Vec4, NodePath, PandaNode,
)
from panda3d.bullet import BulletBoxShape, BulletRigidBodyNode

from .constants import MODEL_BASE

if TYPE_CHECKING:
    from direct.showbase.ShowBase import ShowBase
    from .physics import PhysicsManager


class SceneBuilder:
    """场景构建：地面模型 + 静态障碍物 + 光照。"""

    def __init__(self, base: ShowBase, physics: PhysicsManager) -> None:
        self._base = base
        self._physics = physics

    def build(self) -> None:
        """构建完整场景。"""
        self._load_ground_model()
        self._create_static_obstacles()
        self._setup_lighting()

    def _load_ground_model(self) -> None:
        try:
            ground = self._base.loader.loadModel(f"{MODEL_BASE}/environment")
        except Exception:
            ground = NodePath(PandaNode("ground"))
        ground.setScale(0.25)
        ground.setPos(-8, 42, -1)
        ground.reparentTo(self._base.render)

    def _create_static_obstacles(self) -> None:
        obstacles = [
            (5, 15, -0.5, 1.0),
            (-4, 20, -0.5, 0.8),
            (3, 25, -0.5, 1.2),
            (-6, 12, -0.5, 0.6),
        ]
        for i, (x, y, z, hs) in enumerate(obstacles):
            shape = BulletBoxShape(Vec3(hs, hs, hs))
            body = BulletRigidBodyNode(f"obstacle_{i}")
            body.setMass(0)
            body.addShape(shape)
            body.setFriction(1.0)
            body.setRestitution(0.5)
            obs_np = self._base.render.attachNewNode(body)
            obs_np.setPos(x, y, z)
            self._physics.world.attachRigidBody(body)
            try:
                box_model = self._base.loader.loadModel(f"{MODEL_BASE}/box")
                box_model.setScale(hs * 2)
                box_model.reparentTo(obs_np)
            except Exception:
                pass
            obs_np.setColor(0.6, 0.3, 0.1, 1)

    def _setup_lighting(self) -> None:
        ambient = AmbientLight("ambient")
        ambient.setColor(Vec4(0.3, 0.3, 0.3, 1))
        self._base.render.setLight(self._base.render.attachNewNode(ambient))

        sun = DirectionalLight("sun")
        sun.setColor(Vec4(1, 0.95, 0.8, 1))
        sun.setDirection((-1, -1, -2))
        self._base.render.setLight(self._base.render.attachNewNode(sun))
