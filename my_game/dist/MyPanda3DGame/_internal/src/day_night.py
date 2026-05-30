"""
src/day_night.py — 日夜循环系统
================================
演示 Panda3D 的动态光照参数变化：
- 太阳方向随时间旋转
- 光照颜色渐变（白天暖色 → 夜晚冷色）
- 天空盒 / 雾效颜色联动

引擎对应: DirectionalLight 动态参数 · LerpInterval
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Optional

from panda3d.core import Vec3, Vec4, NodePath, DirectionalLight

if TYPE_CHECKING:
    from direct.showbase.ShowBase import ShowBase
    from .skybox import SkyBox
    from .fog import FogManager


class DayNightCycle:
    """日夜循环管理器。"""

    # 一天的时长（秒），默认 120 秒 = 2 分钟一天
    DEFAULT_DAY_LENGTH = 120.0

    def __init__(self, base: ShowBase) -> None:
        self._base = base
        self._enabled = False
        self._paused = False

        # 时间参数
        self._time_of_day = 0.25  # 0.0~1.0, 0.25=日出, 0.5=正午, 0.75=日落, 0.0=午夜
        self._day_length = self.DEFAULT_DAY_LENGTH
        self._time_speed = 1.0  # 时间倍速

        # 外部引用
        self._sun_np: Optional[NodePath] = None
        self._sun_light: Optional[DirectionalLight] = None
        self._skybox: Optional[SkyBox] = None
        self._fog: Optional[FogManager] = None

        # 光照颜色预设（时间 → 颜色）
        self._sun_colors = {
            0.00: Vec4(0.05, 0.05, 0.15, 1),   # 午夜 — 深蓝
            0.20: Vec4(0.8, 0.4, 0.2, 1),      # 日出 — 橙红
            0.25: Vec4(0.9, 0.7, 0.4, 1),      # 早晨 — 暖黄
            0.50: Vec4(1.0, 0.95, 0.8, 1),     # 正午 — 白色
            0.75: Vec4(0.9, 0.5, 0.2, 1),      # 日落 — 橙色
            0.80: Vec4(0.4, 0.2, 0.3, 1),      # 黄昏 — 紫红
            1.00: Vec4(0.05, 0.05, 0.15, 1),   # 午夜 — 深蓝
        }

        # 环境光颜色预设
        self._ambient_colors = {
            0.00: Vec4(0.02, 0.02, 0.05, 1),
            0.25: Vec4(0.2, 0.2, 0.25, 1),
            0.50: Vec4(0.3, 0.3, 0.3, 1),
            0.75: Vec4(0.2, 0.15, 0.15, 1),
            1.00: Vec4(0.02, 0.02, 0.05, 1),
        }

        # 天空颜色预设
        self._sky_top_colors = {
            0.00: Vec4(0.02, 0.02, 0.1, 1),
            0.25: Vec4(0.3, 0.5, 0.9, 1),
            0.50: Vec4(0.2, 0.4, 0.8, 1),
            0.75: Vec4(0.5, 0.3, 0.4, 1),
            1.00: Vec4(0.02, 0.02, 0.1, 1),
        }

        self._sky_horizon_colors = {
            0.00: Vec4(0.05, 0.05, 0.1, 1),
            0.25: Vec4(0.9, 0.6, 0.3, 1),
            0.50: Vec4(0.7, 0.8, 0.95, 1),
            0.75: Vec4(0.9, 0.5, 0.3, 1),
            1.00: Vec4(0.05, 0.05, 0.1, 1),
        }

    def setup(self, sun_np: NodePath,
              skybox: Optional[SkyBox] = None,
              fog: Optional[FogManager] = None) -> None:
        """
        连接外部系统。

        Parameters
        ----------
        sun_np : NodePath
            方向光 NodePath。
        skybox : SkyBox, optional
            天空盒（颜色联动）。
        fog : FogManager, optional
            雾效（颜色联动）。
        """
        self._sun_np = sun_np
        self._sun_light = sun_np.node()
        self._skybox = skybox
        self._fog = fog

    def enable(self) -> None:
        """启用日夜循环。"""
        self._enabled = True

    def disable(self) -> None:
        """禁用日夜循环。"""
        self._enabled = False

    def toggle(self) -> bool:
        """切换日夜循环。"""
        if self._enabled:
            self.disable()
        else:
            self.enable()
        return self._enabled

    def toggle_pause(self) -> bool:
        """暂停/恢复时间流逝。"""
        self._paused = not self._paused
        return self._paused

    def set_time_speed(self, speed: float) -> None:
        """设置时间倍速 (0.1 ~ 10.0)。"""
        self._time_speed = max(0.1, min(10.0, speed))

    def set_time(self, t: float) -> None:
        """直接设置时间 (0.0 ~ 1.0)。"""
        self._time_of_day = t % 1.0

    @property
    def time_of_day(self) -> float:
        return self._time_of_day

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def time_label(self) -> str:
        """返回当前时间的可读标签。"""
        hour = int(self._time_of_day * 24) % 24
        minute = int((self._time_of_day * 24 * 60) % 60)
        return f"{hour:02d}:{minute:02d}"

    def update(self, dt: float) -> None:
        """每帧更新日夜循环。"""
        if not self._enabled or self._paused:
            return

        # 推进时间
        self._time_of_day += (dt / self._day_length) * self._time_speed
        self._time_of_day %= 1.0

        t = self._time_of_day

        # 更新太阳方向（绕 Y 轴旋转）
        if self._sun_np is not None:
            angle = t * 360.0 - 90.0  # 0.25 时太阳在东方升起
            rad = math.radians(angle)
            dx = -math.cos(rad)
            dz = -math.sin(rad)
            self._sun_light.setDirection(Vec3(dx, -0.3, dz))

            # 更新太阳颜色
            sun_color = self._interpolate_color(self._sun_colors, t)
            self._sun_light.setColor(sun_color)

        # 更新天空盒颜色
        if self._skybox is not None and self._skybox.enabled:
            top = self._interpolate_color(self._sky_top_colors, t)
            horizon = self._interpolate_color(self._sky_horizon_colors, t)
            bottom = Vec4(top.getX() * 0.5, top.getY() * 0.5,
                          top.getZ() * 0.5, 1)
            self._skybox.set_colors(top, horizon, bottom)

        # 更新雾效颜色
        if self._fog is not None and self._fog.enabled:
            fog_color = self._interpolate_color(self._sky_horizon_colors, t)
            self._fog.set_color(fog_color.getX(), fog_color.getY(),
                                fog_color.getZ())

        # 更新背景色（无天空盒时）
        if self._skybox is None or not self._skybox.enabled:
            bg = self._interpolate_color(self._sky_top_colors, t)
            self._base.setBackgroundColor(bg.getX() * 0.3, bg.getY() * 0.3,
                                          bg.getZ() * 0.3, 1)

    def _interpolate_color(self, color_map: dict, t: float) -> Vec4:
        """在颜色预设之间线性插值。"""
        keys = sorted(color_map.keys())

        # 找到 t 所在的区间
        for i in range(len(keys) - 1):
            if keys[i] <= t <= keys[i + 1]:
                t0, t1 = keys[i], keys[i + 1]
                c0, c1 = color_map[t0], color_map[t1]
                f = (t - t0) / (t1 - t0) if t1 != t0 else 0
                return c0 * (1 - f) + c1 * f

        return color_map[keys[0]]
