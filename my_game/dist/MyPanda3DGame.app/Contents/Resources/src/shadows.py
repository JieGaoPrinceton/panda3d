"""
src/shadows.py — 阴影系统管理
================================
演示 Panda3D 的实时阴影渲染能力：
- DirectionalLight.setShadowCaster()
- 阴影贴图分辨率控制
- 阴影开关

引擎对应: samples/shadows/ · DirectionalLight shadow caster
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from panda3d.core import DirectionalLight, NodePath, Vec4, Shader

if TYPE_CHECKING:
    from direct.showbase.ShowBase import ShowBase


class ShadowManager:
    """管理场景阴影渲染。"""

    # 可选的阴影贴图分辨率
    RESOLUTIONS = [512, 1024, 2048, 4096]

    def __init__(self, base: ShowBase) -> None:
        self._base = base
        self._shadow_enabled = False
        self._resolution_idx = 1  # 默认 1024
        self._sun_np: Optional[NodePath] = None
        self._sun_light: Optional[DirectionalLight] = None

    def setup_shadow_light(self, sun_np: NodePath) -> None:
        """
        为已有的方向光启用阴影投射。

        Parameters
        ----------
        sun_np : NodePath
            场景中方向光的 NodePath（由 SceneBuilder 创建）。
        """
        self._sun_np = sun_np
        self._sun_light = sun_np.node()

        # 启用 shader generator（阴影需要自动 shader）
        self._base.render.setShaderAuto()

        # 默认开启阴影
        self.enable_shadows()

    def enable_shadows(self) -> None:
        """开启阴影。"""
        if self._sun_light is None:
            return
        res = self.RESOLUTIONS[self._resolution_idx]
        self._sun_light.setShadowCaster(True, res, res)
        self._shadow_enabled = True

    def disable_shadows(self) -> None:
        """关闭阴影。"""
        if self._sun_light is None:
            return
        self._sun_light.setShadowCaster(False)
        self._shadow_enabled = False

    def toggle_shadows(self) -> bool:
        """切换阴影开关，返回当前状态。"""
        if self._shadow_enabled:
            self.disable_shadows()
        else:
            self.enable_shadows()
        return self._shadow_enabled

    @property
    def enabled(self) -> bool:
        return self._shadow_enabled

    @property
    def resolution(self) -> int:
        return self.RESOLUTIONS[self._resolution_idx]

    def set_resolution(self, idx: int) -> None:
        """设置阴影贴图分辨率（索引 0~3 对应 512~4096）。"""
        self._resolution_idx = max(0, min(idx, len(self.RESOLUTIONS) - 1))
        if self._shadow_enabled:
            # 重新应用
            self.enable_shadows()

    def cycle_resolution(self) -> int:
        """循环切换分辨率，返回新分辨率值。"""
        self._resolution_idx = (self._resolution_idx + 1) % len(self.RESOLUTIONS)
        if self._shadow_enabled:
            self.enable_shadows()
        return self.resolution
