"""
src/collectibles.py — 可拾取经验方块生成与管理
"""

from __future__ import annotations

import random
from typing import List, Dict, Optional, TYPE_CHECKING

from panda3d.core import Vec3, NodePath
from panda3d.bullet import BulletBoxShape, BulletRigidBodyNode

from .constants import (
    MODEL_BASE,
    GEM_SPAWN_INTERVAL,
    GEM_MAX_COUNT,
    GEM_SPAWN_RANGE_X,
    GEM_SPAWN_RANGE_Y,
    GEM_SPAWN_HEIGHT,
    GEM_EXP_MIN,
    GEM_EXP_MAX,
    GEM_COLLECT_DISTANCE,
)

if TYPE_CHECKING:
    from direct.showbase.ShowBase import ShowBase
    from .physics import PhysicsManager
    from .player import PlayerController
    from .audio import AudioManager


class CollectibleManager:
    """管理场景中随机生成的可拾取经验方块。

    方块以 ``gem_`` 前缀命名，与普通 ``box_`` 方块区分。
    玩家靠近方块时自动拾取，获得随机经验值。
    """

    def __init__(
        self,
        base: ShowBase,
        physics: PhysicsManager,
        player: PlayerController,
        audio: AudioManager,
    ) -> None:
        self._base = base
        self._physics = physics
        self._player = player
        self._audio = audio

        self._gems: List[NodePath] = []
        self._gem_exp: Dict[str, int] = {}   # node_name → exp
        self._gem_counter = 0
        self._spawn_timer = 0.0

    # ── 公开属性 ──────────────────────────────

    @property
    def gem_count(self) -> int:
        return len(self._gems)

    def get_exp(self, node_name: str) -> int:
        """返回指定方块携带的经验值。"""
        return self._gem_exp.get(node_name, 0)

    # ── 生成 ──────────────────────────────────

    def _spawn_gem(self) -> None:
        """在随机位置生成一个经验方块。"""
        if len(self._gems) >= GEM_MAX_COUNT:
            return

        self._gem_counter += 1
        name = f"gem_{self._gem_counter}"

        # 随机经验值
        exp = random.randint(GEM_EXP_MIN, GEM_EXP_MAX)
        self._gem_exp[name] = exp

        # 随机位置
        x = random.uniform(*GEM_SPAWN_RANGE_X)
        y = random.uniform(*GEM_SPAWN_RANGE_Y)
        z = GEM_SPAWN_HEIGHT

        # 物理体 — 小方块
        size = 0.35
        shape = BulletBoxShape(Vec3(size, size, size))
        body = BulletRigidBodyNode(name)
        body.setMass(0.5)
        body.addShape(shape)
        body.setFriction(1.0)
        body.setRestitution(0.2)

        gem_np = self._base.render.attachNewNode(body)
        gem_np.setPos(x, y, z)
        self._physics.world.attachRigidBody(body)

        # 加载模型
        try:
            model = self._base.loader.loadModel(f"{MODEL_BASE}/box")
            model.setScale(size * 2)
            model.reparentTo(gem_np)
        except Exception:
            pass

        # 根据经验值设置颜色：低经验偏绿，高经验偏金
        ratio = (exp - GEM_EXP_MIN) / max(1, GEM_EXP_MAX - GEM_EXP_MIN)
        r = 0.2 + ratio * 0.8       # 0.2 → 1.0
        g = 1.0 - ratio * 0.3       # 1.0 → 0.7
        b = 0.1                      # 始终偏低
        gem_np.setColor(r, g, b, 1)

        self._gems.append(gem_np)

    # ── 拾取检测 ──────────────────────────────

    def _check_collect(self) -> Optional[int]:
        """检测玩家是否靠近经验方块，自动拾取并返回获得的经验值。"""
        player_pos = self._player.physics_np.getPos()
        collected_exp = 0

        to_remove = []
        for gem_np in self._gems:
            if gem_np.isEmpty():
                to_remove.append(gem_np)
                continue
            dist = (gem_np.getPos() - player_pos).length()
            if dist < GEM_COLLECT_DISTANCE:
                name = gem_np.node().getName()
                exp = self._gem_exp.pop(name, 0)
                collected_exp += exp

                # 从物理世界移除
                body = gem_np.node()
                if isinstance(body, BulletRigidBodyNode):
                    self._physics.world.removeRigidBody(body)
                gem_np.removeNode()
                to_remove.append(gem_np)

        for g in to_remove:
            if g in self._gems:
                self._gems.remove(g)

        return collected_exp if collected_exp > 0 else None

    # ── 点击拾取 ──────────────────────────────

    def try_collect_by_name(self, node_name: str) -> Optional[int]:
        """通过节点名称拾取经验方块（鼠标点击），返回经验值或 None。"""
        if not node_name.startswith("gem_"):
            return None

        for gem_np in self._gems:
            if gem_np.isEmpty():
                continue
            if gem_np.node().getName() == node_name:
                exp = self._gem_exp.pop(node_name, 0)
                body = gem_np.node()
                if isinstance(body, BulletRigidBodyNode):
                    self._physics.world.removeRigidBody(body)
                gem_np.removeNode()
                self._gems.remove(gem_np)
                return exp
        return None

    # ── 每帧更新 ──────────────────────────────

    def update(self, dt: float) -> Optional[int]:
        """每帧调用：定时生成 + 自动拾取检测。

        返回本帧获得的经验值（无则返回 None）。
        """
        # 定时生成
        self._spawn_timer += dt
        if self._spawn_timer >= GEM_SPAWN_INTERVAL:
            self._spawn_timer = 0.0
            self._spawn_gem()

        # 自动拾取
        return self._check_collect()
