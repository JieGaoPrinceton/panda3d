"""
src/scene.py — 场景构建
========================
职责:
    - 加载地面环境模型
    - 创建静态障碍物（Bullet 静态刚体 + 可视模型）
    - 设置光照（环境光 + 方向光/太阳）

引擎对应: panda3d.core.AmbientLight · DirectionalLight · panda3d.bullet
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

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
    """场景构建器：地面模型 + 静态障碍物 + 光照。

    Attributes
    ----------
    sun_np : NodePath | None
        方向光（太阳）的场景节点。
        供阴影系统（ShadowManager）和日夜循环（DayNightCycle）使用。
    """

    def __init__(self, base: ShowBase, physics: PhysicsManager) -> None:
        self._base = base
        self._physics = physics
        self.sun_np: Optional[NodePath] = None

    def build(self) -> None:
        """构建完整场景（地面 + 障碍物 + 光照）。"""
        self._load_ground_model()
        self._create_static_obstacles()
        self._setup_lighting()

    # ──────────────────────────────────────────────────────────
    # 地面
    # ──────────────────────────────────────────────────────────

    def _load_ground_model(self) -> None:
        """加载地面环境模型（Panda3D 自带的 environment 模型）。"""
        try:
            ground = self._base.loader.loadModel(f"{MODEL_BASE}/environment")
        except Exception:
            ground = NodePath(PandaNode("ground"))
        ground.setScale(0.25)
        ground.setPos(-8, 42, -1)  # 调整位置使地面与物理平面对齐
        ground.reparentTo(self._base.render)

    # ──────────────────────────────────────────────────────────
    # 静态障碍物
    # ──────────────────────────────────────────────────────────

    def _create_static_obstacles(self) -> None:
        """创建 4 个静态障碍物方块。

        每个障碍物由 Bullet 静态刚体（mass=0）+ 可视模型组成。
        格式: (x, y, z, half_size)
        """
        obstacles = [
            (5, 15, -0.5, 1.0),
            (-4, 20, -0.5, 0.8),
            (3, 25, -0.5, 1.2),
            (-6, 12, -0.5, 0.6),
        ]
        for i, (x, y, z, hs) in enumerate(obstacles):
            # 物理体（静态，mass=0）
            shape = BulletBoxShape(Vec3(hs, hs, hs))
            body = BulletRigidBodyNode(f"obstacle_{i}")
            body.setMass(0)
            body.addShape(shape)
            body.setFriction(1.0)
            body.setRestitution(0.5)

            obs_np = self._base.render.attachNewNode(body)
            obs_np.setPos(x, y, z)
            self._physics.world.attachRigidBody(body)

            # 可视模型
            try:
                box_model = self._base.loader.loadModel(f"{MODEL_BASE}/box")
                box_model.setScale(hs * 2)
                box_model.reparentTo(obs_np)
            except Exception:
                pass
            obs_np.setColor(0.6, 0.3, 0.1, 1)  # 棕色

    # ──────────────────────────────────────────────────────────
    # 光照
    # ──────────────────────────────────────────────────────────

    def _setup_lighting(self) -> None:
        """设置场景光照。

        - 环境光: 低强度全局照明，防止阴影区域全黑
        - 方向光（太阳）: 主光源，暖白色，从左上方照射
          sun_np 暴露给外部系统（阴影、日夜循环）使用
        """
        # 环境光（全局柔和照明）
        ambient = AmbientLight("ambient")
        ambient.setColor(Vec4(0.3, 0.3, 0.3, 1))
        self._base.render.setLight(self._base.render.attachNewNode(ambient))

        # 方向光（太阳）
        sun = DirectionalLight("sun")
        sun.setColor(Vec4(1, 0.95, 0.8, 1))  # 暖白色
        sun.setDirection((-1, -1, -2))         # 从左上方照射
        self.sun_np = self._base.render.attachNewNode(sun)
        self._base.render.setLight(self.sun_np)
