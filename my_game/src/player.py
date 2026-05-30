"""
src/player.py — 玩家控制（移动 + 跳跃 + 地面检测）
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from panda3d.core import Vec3, Point3, NodePath, PandaNode
from panda3d.bullet import BulletSphereShape, BulletRigidBodyNode
from direct.actor.Actor import Actor

from .constants import MODEL_BASE, DEFAULTS, PLAYER_SPEED

if TYPE_CHECKING:
    from .physics import PhysicsManager


class PlayerController:
    """玩家物理体 + 移动 + 跳跃 + 经验值。"""

    def __init__(self, base, physics: PhysicsManager) -> None:
        self._base = base
        self._physics = physics

        self.mass = DEFAULTS["player_mass"]
        self.friction = DEFAULTS["player_friction"]
        self.restitution = DEFAULTS["player_restitution"]
        self.jump_force = DEFAULTS["jump_force"]
        self.speed = PLAYER_SPEED

        # 经验值系统
        self.exp: int = 0

        # 创建物理体
        shape = BulletSphereShape(0.5)
        body = BulletRigidBodyNode("player_physics")
        body.setMass(self.mass)
        body.addShape(shape)
        body.setFriction(self.friction)
        body.setRestitution(self.restitution)
        body.setAngularFactor(Vec3(0, 0, 0))

        self.physics_np = base.render.attachNewNode(body)
        self.physics_np.setPos(0, 10, 2)
        physics.world.attachRigidBody(body)

        # 加载模型
        try:
            self.model = Actor(
                f"{MODEL_BASE}/panda-model",
                {"walk": f"{MODEL_BASE}/panda-walk4"},
            )
            self.model.loop("walk")
        except Exception:
            self.model = NodePath(PandaNode("player"))
        self.model.setScale(0.005)
        self.model.setZ(-0.5)
        self.model.reparentTo(self.physics_np)

        # 相机跟随点
        self.floater = NodePath(PandaNode("floater"))
        self.floater.reparentTo(self.physics_np)
        self.floater.setZ(2.0)

    def is_on_ground(self) -> bool:
        """Bullet 射线检测是否在地面上。"""
        pos = self.physics_np.getPos()
        from_pt = Point3(pos.getX(), pos.getY(), pos.getZ())
        to_pt = Point3(pos.getX(), pos.getY(), pos.getZ() - 1.2)
        result = self._physics.world.rayTestClosest(from_pt, to_pt)
        return result.hasHit()

    def jump(self) -> bool:
        """尝试跳跃，返回是否成功。"""
        if self.is_on_ground():
            body = self.physics_np.node()
            body.setActive(True)
            vel = body.getLinearVelocity()
            body.setLinearVelocity(
                Vec3(vel.getX(), vel.getY(), self.jump_force)
            )
            return True
        return False

    def update(self, keys: dict) -> None:
        """每帧更新玩家移动。"""
        body = self.physics_np.node()
        body.setActive(True)

        velocity = body.getLinearVelocity()
        vx, vy = 0.0, 0.0
        if keys["forward"]:
            vy = self.speed
        if keys["backward"]:
            vy = -self.speed
        if keys["left"]:
            vx = -self.speed
        if keys["right"]:
            vx = self.speed

        body.setLinearVelocity(Vec3(vx, vy, velocity.getZ()))

    def add_exp(self, amount: int) -> None:
        """增加经验值。"""
        self.exp += amount

    def get_spawn_pos(self) -> Vec3:
        """获取方块生成位置（玩家前方上方）。"""
        px = self.physics_np.getX()
        py = self.physics_np.getY()
        pz = self.physics_np.getZ()
        return Vec3(px, py + 3, pz + 5)
