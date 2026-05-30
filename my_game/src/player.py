"""
src/player.py — 玩家控制器
===========================
职责:
    - 创建玩家物理体（BulletSphereShape）
    - 加载 Panda 模型 + 行走动画
    - WASD 移动（方向跟随相机 heading）
    - 跳跃 + 地面检测（Bullet 射线）
    - 经验值管理

引擎对应: panda3d.bullet · direct.actor.Actor
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from panda3d.core import Vec3, Point3, NodePath, PandaNode
from panda3d.bullet import BulletSphereShape, BulletRigidBodyNode
from direct.actor.Actor import Actor

from .constants import MODEL_BASE, DEFAULTS, PLAYER_SPEED

if TYPE_CHECKING:
    from .physics import PhysicsManager


class PlayerController:
    """玩家物理体 + 移动 + 跳跃 + 经验值。

    Attributes
    ----------
    physics_np : NodePath
        玩家物理体的场景节点（Bullet 刚体）。
    model : Actor | NodePath
        玩家可视模型（Panda 模型 + 行走动画）。
    floater : NodePath
        相机跟随点（位于玩家头顶上方）。
    exp : int
        当前经验值。
    """

    def __init__(self, base, physics: PhysicsManager) -> None:
        self._base = base
        self._physics = physics

        # 从常量加载物理参数
        self.mass = DEFAULTS["player_mass"]
        self.friction = DEFAULTS["player_friction"]
        self.restitution = DEFAULTS["player_restitution"]
        self.jump_force = DEFAULTS["jump_force"]
        self.speed = PLAYER_SPEED

        # 经验值
        self.exp: int = 0

        # ── 创建物理体 ──
        # 使用球形碰撞体，锁定角速度防止翻滚
        shape = BulletSphereShape(0.5)
        body = BulletRigidBodyNode("player_physics")
        body.setMass(self.mass)
        body.addShape(shape)
        body.setFriction(self.friction)
        body.setRestitution(self.restitution)
        body.setAngularFactor(Vec3(0, 0, 0))  # 锁定旋转，防止物理体翻滚

        self.physics_np = base.render.attachNewNode(body)
        self.physics_np.setPos(0, 10, 2)  # 初始出生点
        physics.world.attachRigidBody(body)

        # ── 加载可视模型 ──
        try:
            self.model = Actor(
                f"{MODEL_BASE}/panda-model",
                {"walk": f"{MODEL_BASE}/panda-walk4"},
            )
            self.model.loop("walk")
        except Exception:
            self.model = NodePath(PandaNode("player"))
        self.model.setScale(0.005)
        self.model.setZ(-0.5)  # 模型底部对齐物理体底部
        self.model.reparentTo(self.physics_np)

        # ── 相机跟随点 ──
        # 位于玩家头顶上方，供相机 lookAt 使用
        self.floater = NodePath(PandaNode("floater"))
        self.floater.reparentTo(self.physics_np)
        self.floater.setZ(2.0)

    # ──────────────────────────────────────────────────────────
    # 地面检测
    # ──────────────────────────────────────────────────────────

    def is_on_ground(self) -> bool:
        """Bullet 射线检测：从玩家脚底向下发射短射线，判断是否接触地面。"""
        pos = self.physics_np.getPos()
        from_pt = Point3(pos.getX(), pos.getY(), pos.getZ())
        to_pt = Point3(pos.getX(), pos.getY(), pos.getZ() - 1.2)
        result = self._physics.world.rayTestClosest(from_pt, to_pt)
        return result.hasHit()

    # ──────────────────────────────────────────────────────────
    # 跳跃
    # ──────────────────────────────────────────────────────────

    def jump(self) -> bool:
        """尝试跳跃。仅在地面上时生效，返回是否成功。"""
        if self.is_on_ground():
            body = self.physics_np.node()
            body.setActive(True)
            vel = body.getLinearVelocity()
            # 保持水平速度，仅设置垂直速度
            body.setLinearVelocity(
                Vec3(vel.getX(), vel.getY(), self.jump_force)
            )
            return True
        return False

    # ──────────────────────────────────────────────────────────
    # 每帧移动
    # ──────────────────────────────────────────────────────────

    def update(self, keys: dict, cam_heading: float = 180.0) -> None:
        """每帧更新玩家移动。

        WASD 输入方向会根据相机 heading 旋转到世界坐标系，
        使"前进"始终朝相机正前方。

        Parameters
        ----------
        keys : dict
            按键状态 {"forward": bool, "backward": bool, "left": bool, "right": bool}。
        cam_heading : float
            相机的 heading 角度（度）。用于将局部输入旋转到世界坐标。
        """
        body = self.physics_np.node()
        body.setActive(True)

        velocity = body.getLinearVelocity()

        # 1. 在相机局部坐标系中计算输入方向
        #    local_y: +1=前进, -1=后退
        #    local_x: -1=左, +1=右
        local_x, local_y = 0.0, 0.0
        if keys["forward"]:
            local_y += 1.0
        if keys["backward"]:
            local_y -= 1.0
        if keys["left"]:
            local_x -= 1.0
        if keys["right"]:
            local_x += 1.0

        # 无输入时停止水平移动
        if local_x == 0.0 and local_y == 0.0:
            body.setLinearVelocity(Vec3(0, 0, velocity.getZ()))
            return

        # 2. 归一化对角线输入（防止斜向移动加速 √2 倍）
        length = math.sqrt(local_x * local_x + local_y * local_y)
        local_x /= length
        local_y /= length

        # 3. 将局部方向旋转到世界坐标
        #    相机位置公式: cam_x = t.x + d*cos(p)*sin(h), cam_y = t.y - d*cos(p)*cos(h)
        #    相机看向方向 = target - cam = (-d*cos(p)*sin(h), +d*cos(p)*cos(h), ...)
        #    即相机前方单位向量 = (-sin(h), cos(h))
        #    相机右方单位向量 = (cos(h), sin(h))
        #
        #    local_y=+1(前进) → 沿相机前方: (-sin(h), cos(h))
        #    local_x=+1(右移) → 沿相机右方: (cos(h), sin(h))
        #
        #    world = local_x * right + local_y * forward
        #          = local_x * (cos_h, sin_h) + local_y * (-sin_h, cos_h)
        rad = math.radians(cam_heading)
        sin_h = math.sin(rad)
        cos_h = math.cos(rad)

        world_x = local_x * cos_h - local_y * sin_h
        world_y = local_x * sin_h + local_y * cos_h

        # 4. 应用速度
        vx = world_x * self.speed
        vy = world_y * self.speed
        body.setLinearVelocity(Vec3(vx, vy, velocity.getZ()))

        # 5. 模型面朝移动方向
        #    Panda3D 的 heading: 0°=+Y, 90°=-X, 180°=-Y, 270°=+X
        #    atan2(-world_x, world_y) 给出移动方向的 heading
        #    熊猫模型默认面朝 -Y，需要额外偏移 180° 使其面朝移动方向
        move_heading = math.degrees(math.atan2(-world_x, world_y)) + 180.0
        self.model.setH(move_heading)

    # ──────────────────────────────────────────────────────────
    # 经验值
    # ──────────────────────────────────────────────────────────

    def add_exp(self, amount: int) -> None:
        """增加经验值。"""
        self.exp += amount

    # ──────────────────────────────────────────────────────────
    # 方块生成位置
    # ──────────────────────────────────────────────────────────

    def get_spawn_pos(self) -> Vec3:
        """获取方块生成位置（玩家面朝方向的前方上方）。"""
        px = self.physics_np.getX()
        py = self.physics_np.getY()
        pz = self.physics_np.getZ()
        # 使用模型的 heading 确定前方方向
        h_rad = math.radians(self.model.getH())
        forward_x = math.sin(h_rad)
        forward_y = math.cos(h_rad)
        return Vec3(px - forward_x * 3, py + forward_y * 3, pz + 5)
