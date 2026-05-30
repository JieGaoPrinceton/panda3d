"""
src/fog.py — 雾效系统
======================
演示 Panda3D 的 Fog 节点：
- 线性雾 (Linear Fog)
- 指数雾 (Exponential Fog)
- 雾颜色 / 密度 / 范围可调

引擎对应: samples/infinite-tunnel/ · panda3d.core.Fog
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from panda3d.core import Fog, Vec4

if TYPE_CHECKING:
    from direct.showbase.ShowBase import ShowBase


class FogManager:
    """场景雾效管理。"""

    def __init__(self, base: ShowBase) -> None:
        self._base = base
        self._enabled = False

        # 线性雾参数
        self._linear_onset = 30.0   # 雾开始距离
        self._linear_opaque = 120.0  # 完全不透明距离

        # 指数雾参数
        self._exp_density = 0.01

        # 雾颜色（默认浅灰蓝）
        self._fog_color = Vec4(0.6, 0.65, 0.75, 1.0)

        # 雾模式: "linear" 或 "exponential"
        self._mode = "linear"

        # 创建雾节点
        self._fog = Fog("scene_fog")
        self._apply_params()

    def _apply_params(self) -> None:
        """应用当前参数到雾节点。"""
        self._fog.setColor(self._fog_color)

        if self._mode == "linear":
            self._fog.setLinearRange(self._linear_onset, self._linear_opaque)
            self._fog.setLinearFallback(45, 160, 320)
        else:
            self._fog.setExpDensity(self._exp_density)

    def enable(self) -> None:
        """开启雾效。"""
        self._apply_params()
        self._base.render.setFog(self._fog)
        self._enabled = True

    def disable(self) -> None:
        """关闭雾效。"""
        self._base.render.clearFog()
        self._enabled = False

    def toggle(self) -> bool:
        """切换雾效开关，返回当前状态。"""
        if self._enabled:
            self.disable()
        else:
            self.enable()
        return self._enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str) -> None:
        """设置雾模式: 'linear' 或 'exponential'。"""
        if mode in ("linear", "exponential"):
            self._mode = mode
            if self._enabled:
                self._apply_params()
                self._base.render.setFog(self._fog)

    def toggle_mode(self) -> str:
        """切换雾模式。"""
        new_mode = "exponential" if self._mode == "linear" else "linear"
        self.set_mode(new_mode)
        return self._mode

    def set_color(self, r: float, g: float, b: float) -> None:
        """设置雾颜色。"""
        self._fog_color = Vec4(r, g, b, 1.0)
        if self._enabled:
            self._apply_params()
            self._base.render.setFog(self._fog)

    def set_linear_range(self, onset: float, opaque: float) -> None:
        """设置线性雾范围。"""
        self._linear_onset = onset
        self._linear_opaque = opaque
        if self._enabled and self._mode == "linear":
            self._apply_params()
            self._base.render.setFog(self._fog)

    def set_exp_density(self, density: float) -> None:
        """设置指数雾密度。"""
        self._exp_density = density
        if self._enabled and self._mode == "exponential":
            self._apply_params()
            self._base.render.setFog(self._fog)

    @property
    def linear_onset(self) -> float:
        return self._linear_onset

    @property
    def linear_opaque(self) -> float:
        return self._linear_opaque

    @property
    def exp_density(self) -> float:
        return self._exp_density
