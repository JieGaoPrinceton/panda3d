"""
src/particles_fx.py — 粒子特效系统
====================================
演示 Panda3D 的粒子系统：
- 跳跃落地尘土
- 经验拾取星光
- 方块碰撞火花

引擎对应: samples/particles/ · direct.particles · panda3d.physics
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from panda3d.core import Vec3, Vec4, Point3, NodePath, PandaNode
from panda3d.physics import (
    BaseParticleEmitter, BaseParticleRenderer,
    PointParticleFactory, SpriteParticleRenderer,
    SphereSurfaceEmitter, PointEmitter,
    LinearVectorForce, ForceNode,
)
from direct.particles.ParticleEffect import ParticleEffect
from direct.particles.Particles import Particles

if TYPE_CHECKING:
    from direct.showbase.ShowBase import ShowBase


class ParticleFXManager:
    """粒子特效管理器。"""

    def __init__(self, base: ShowBase) -> None:
        self._base = base
        self._enabled = True

        # 启用粒子系统
        base.enableParticles()

    def create_dust_effect(self, pos: Point3) -> ParticleEffect:
        """
        跳跃落地时的尘土效果。

        Parameters
        ----------
        pos : Point3
            粒子发射位置（玩家脚下）。
        """
        if not self._enabled:
            return None

        effect = ParticleEffect()
        effect.reset()
        effect.setPos(pos)

        # 创建粒子组
        p = Particles("dust")
        p.setPoolSize(30)
        p.setBirthRate(0.0)  # 一次性爆发
        p.setLitterSize(20)
        p.setLitterSpread(5)
        p.setSystemLifespan(0.8)
        p.setLocalVelocityFlag(True)
        p.setSystemGrowsOlderFlag(True)

        # 工厂 — 粒子属性
        factory = PointParticleFactory()
        factory.setLifespanBase(0.5)
        factory.setLifespanSpread(0.3)
        factory.setMassBase(0.5)
        factory.setMassSpread(0.2)
        factory.setTerminalVelocityBase(2.0)
        factory.setTerminalVelocitySpread(1.0)
        p.setFactory(factory)

        # 发射器 — 球面发射
        emitter = SphereSurfaceEmitter()
        emitter.setRadius(0.5)
        emitter.setEmissionType(BaseParticleEmitter.ETRADIATE)
        p.setEmitter(emitter)

        # 渲染器 — 点渲染
        renderer = SpriteParticleRenderer()
        renderer.setColor(Vec4(0.7, 0.6, 0.4, 0.8))
        renderer.setAlphaMode(BaseParticleRenderer.PRALPHAOUT)
        p.setRenderer(renderer)

        effect.addParticles(p)

        # 添加重力
        gravity_node = ForceNode("dust_gravity")
        gravity_force = LinearVectorForce(Vec3(0, 0, -3.0))
        gravity_force.setMassDependent(False)
        gravity_node.addForce(gravity_force)
        gravity_np = self._base.render.attachNewNode(gravity_node)
        effect.addForceGroup(gravity_np)

        effect.reparentTo(self._base.render)
        effect.start(self._base.render)

        # 自动清理
        self._base.taskMgr.doMethodLater(
            1.0, self._cleanup_effect, "cleanup_dust",
            extraArgs=[effect, gravity_np], appendTask=True,
        )

        return effect

    def create_sparkle_effect(self, pos: Point3) -> ParticleEffect:
        """
        经验拾取时的星光爆发效果。

        Parameters
        ----------
        pos : Point3
            粒子发射位置。
        """
        if not self._enabled:
            return None

        effect = ParticleEffect()
        effect.reset()
        effect.setPos(pos)

        p = Particles("sparkle")
        p.setPoolSize(40)
        p.setBirthRate(0.0)
        p.setLitterSize(30)
        p.setLitterSpread(10)
        p.setSystemLifespan(1.0)
        p.setLocalVelocityFlag(True)
        p.setSystemGrowsOlderFlag(True)

        factory = PointParticleFactory()
        factory.setLifespanBase(0.8)
        factory.setLifespanSpread(0.4)
        factory.setMassBase(0.3)
        factory.setMassSpread(0.1)
        factory.setTerminalVelocityBase(4.0)
        factory.setTerminalVelocitySpread(2.0)
        p.setFactory(factory)

        emitter = SphereSurfaceEmitter()
        emitter.setRadius(0.3)
        emitter.setEmissionType(BaseParticleEmitter.ETRADIATE)
        p.setEmitter(emitter)

        renderer = SpriteParticleRenderer()
        renderer.setColor(Vec4(1.0, 0.9, 0.3, 1.0))  # 金色
        renderer.setAlphaMode(BaseParticleRenderer.PRALPHAOUT)
        p.setRenderer(renderer)

        effect.addParticles(p)
        effect.reparentTo(self._base.render)
        effect.start(self._base.render)

        self._base.taskMgr.doMethodLater(
            1.5, self._cleanup_effect, "cleanup_sparkle",
            extraArgs=[effect], appendTask=True,
        )

        return effect

    def create_impact_effect(self, pos: Point3) -> ParticleEffect:
        """
        方块碰撞时的火花效果。

        Parameters
        ----------
        pos : Point3
            碰撞位置。
        """
        if not self._enabled:
            return None

        effect = ParticleEffect()
        effect.reset()
        effect.setPos(pos)

        p = Particles("impact")
        p.setPoolSize(20)
        p.setBirthRate(0.0)
        p.setLitterSize(15)
        p.setLitterSpread(5)
        p.setSystemLifespan(0.5)
        p.setLocalVelocityFlag(True)
        p.setSystemGrowsOlderFlag(True)

        factory = PointParticleFactory()
        factory.setLifespanBase(0.3)
        factory.setLifespanSpread(0.2)
        factory.setMassBase(0.2)
        factory.setMassSpread(0.1)
        factory.setTerminalVelocityBase(6.0)
        factory.setTerminalVelocitySpread(3.0)
        p.setFactory(factory)

        emitter = SphereSurfaceEmitter()
        emitter.setRadius(0.2)
        emitter.setEmissionType(BaseParticleEmitter.ETRADIATE)
        p.setEmitter(emitter)

        renderer = SpriteParticleRenderer()
        renderer.setColor(Vec4(1.0, 0.5, 0.1, 1.0))  # 橙色火花
        renderer.setAlphaMode(BaseParticleRenderer.PRALPHAOUT)
        p.setRenderer(renderer)

        effect.addParticles(p)
        effect.reparentTo(self._base.render)
        effect.start(self._base.render)

        self._base.taskMgr.doMethodLater(
            0.8, self._cleanup_effect, "cleanup_impact",
            extraArgs=[effect], appendTask=True,
        )

        return effect

    def _cleanup_effect(self, *args) -> None:
        """清理粒子效果。"""
        task = args[-1]
        nodes = args[:-1]
        for node in nodes:
            if node and not node.isEmpty():
                node.cleanup()
                node.removeNode()
        return task.done

    def toggle(self) -> bool:
        """切换粒子系统开关。"""
        self._enabled = not self._enabled
        return self._enabled

    @property
    def enabled(self) -> bool:
        return self._enabled
