"""
src/animations.py — Interval 动画系统
======================================
演示 Panda3D 的 Interval 动画框架：
- LerpInterval (位置/旋转/缩放/颜色 插值)
- Sequence / Parallel (组合动画)
- Func / Wait (函数调用 + 等待)

引擎对应: samples/carousel/ · direct.interval.*
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from panda3d.core import NodePath, Vec3, Vec4, Point3
from direct.interval.IntervalGlobal import (
    Sequence, Parallel, Func, Wait,
    LerpPosInterval, LerpHprInterval,
    LerpScaleInterval, LerpColorScaleInterval,
    LerpColorInterval,
)

if TYPE_CHECKING:
    from direct.showbase.ShowBase import ShowBase


class AnimationManager:
    """管理游戏中的 Interval 动画。"""

    def __init__(self, base: ShowBase) -> None:
        self._base = base

    # ── 方块生成弹跳动画 ──
    def spawn_bounce(self, node: NodePath) -> None:
        """
        方块生成时的弹跳缩放动画。
        从 0 弹到 1.2 再回到 1.0。
        """
        original_scale = node.getScale()
        sx, sy, sz = original_scale.getX(), original_scale.getY(), original_scale.getZ()

        seq = Sequence(
            LerpScaleInterval(node, 0.15, Vec3(sx * 1.3, sy * 1.3, sz * 1.3),
                              startScale=Vec3(0.01, 0.01, 0.01),
                              blendType="easeOut"),
            LerpScaleInterval(node, 0.1, Vec3(sx * 0.9, sy * 0.9, sz * 0.9),
                              blendType="easeInOut"),
            LerpScaleInterval(node, 0.1, original_scale,
                              blendType="easeInOut"),
        )
        seq.start()

    # ── 经验拾取浮动文字动画 ──
    def exp_float_up(self, text_node: NodePath, start_pos: Point3,
                     duration: float = 1.5) -> None:
        """
        经验值文字向上浮动 + 淡出动画。
        """
        end_pos = Point3(start_pos.getX(), start_pos.getY(),
                         start_pos.getZ() + 2.0)

        seq = Sequence(
            Parallel(
                LerpPosInterval(text_node, duration, end_pos,
                                startPos=start_pos, blendType="easeOut"),
                Sequence(
                    Wait(duration * 0.6),
                    LerpColorScaleInterval(text_node, duration * 0.4,
                                           Vec4(1, 1, 1, 0),
                                           startColorScale=Vec4(1, 1, 1, 1)),
                ),
            ),
            Func(text_node.hide),
        )
        seq.start()

    # ── 物体高亮闪烁动画 ──
    def highlight_pulse(self, node: NodePath, color: Vec4 = None,
                        duration: float = 0.5) -> None:
        """
        选中物体时的颜色脉冲动画。
        """
        if color is None:
            color = Vec4(1, 1, 0.3, 1)

        original_color = Vec4(1, 1, 1, 1)

        seq = Sequence(
            LerpColorScaleInterval(node, duration * 0.5, color,
                                   startColorScale=original_color),
            LerpColorScaleInterval(node, duration * 0.5, original_color,
                                   startColorScale=color),
        )
        seq.start()

    # ── 相机平滑过渡 ──
    def camera_transition(self, camera: NodePath,
                          target_pos: Point3, target_hpr: Vec3,
                          duration: float = 0.5) -> None:
        """
        相机模式切换时的平滑过渡动画。
        """
        par = Parallel(
            LerpPosInterval(camera, duration, target_pos,
                            blendType="easeInOut"),
            LerpHprInterval(camera, duration, target_hpr,
                            blendType="easeInOut"),
        )
        par.start()

    # ── 旋转动画（展示用） ──
    def spin(self, node: NodePath, duration: float = 4.0,
             axis: str = "h") -> None:
        """
        让物体持续旋转（用于展示经验方块等）。
        """
        if axis == "h":
            hpr = Vec3(360, 0, 0)
        elif axis == "p":
            hpr = Vec3(0, 360, 0)
        else:
            hpr = Vec3(0, 0, 360)

        interval = LerpHprInterval(node, duration, hpr,
                                   startHpr=Vec3(0, 0, 0))
        interval.loop()
        return interval

    # ── 缩放呼吸动画 ──
    def breathe(self, node: NodePath, scale_range: float = 0.1,
                duration: float = 2.0) -> None:
        """
        物体缩放呼吸效果（经验方块悬浮感）。
        """
        base_scale = node.getScale()
        sx, sy, sz = base_scale.getX(), base_scale.getY(), base_scale.getZ()
        big = Vec3(sx * (1 + scale_range), sy * (1 + scale_range),
                   sz * (1 + scale_range))
        small = Vec3(sx * (1 - scale_range * 0.5), sy * (1 - scale_range * 0.5),
                     sz * (1 - scale_range * 0.5))

        seq = Sequence(
            LerpScaleInterval(node, duration * 0.5, big,
                              blendType="easeInOut"),
            LerpScaleInterval(node, duration * 0.5, small,
                              blendType="easeInOut"),
        )
        seq.loop()
        return seq

    # ── 震动效果 ──
    def shake(self, node: NodePath, intensity: float = 0.3,
              duration: float = 0.3) -> None:
        """
        物体震动效果（受击/碰撞反馈）。
        """
        original_pos = node.getPos()
        ox, oy, oz = original_pos.getX(), original_pos.getY(), original_pos.getZ()

        seq = Sequence(
            LerpPosInterval(node, duration * 0.1,
                            Point3(ox + intensity, oy, oz)),
            LerpPosInterval(node, duration * 0.1,
                            Point3(ox - intensity, oy, oz)),
            LerpPosInterval(node, duration * 0.1,
                            Point3(ox, oy + intensity, oz)),
            LerpPosInterval(node, duration * 0.1,
                            Point3(ox, oy - intensity, oz)),
            LerpPosInterval(node, duration * 0.1, original_pos),
        )
        seq.start()
