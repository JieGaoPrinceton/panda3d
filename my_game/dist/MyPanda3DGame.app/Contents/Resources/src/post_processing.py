"""
src/post_processing.py — 后处理滤镜系统
========================================
演示 Panda3D 的 CommonFilters 后处理管线：
- Bloom 泛光
- 环境光遮蔽 (AO)
- 反转颜色
- 模糊

引擎对应: samples/glow-filter/ · direct.filter.CommonFilters
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from direct.filter.CommonFilters import CommonFilters

if TYPE_CHECKING:
    from direct.showbase.ShowBase import ShowBase


class PostProcessing:
    """后处理滤镜管理。"""

    def __init__(self, base: ShowBase) -> None:
        self._base = base
        self._filters: Optional[CommonFilters] = None
        self._initialized = False

        # 各滤镜状态
        self._bloom_enabled = False
        self._bloom_intensity = 0.5
        self._bloom_size = "medium"  # small / medium / large

        self._ao_enabled = False
        self._ao_strength = 0.5
        self._ao_radius = 0.05

        self._blur_enabled = False
        self._blur_amount = 0.5

        self._inverted = False

        self._hdr_enabled = False

    def _ensure_filters(self) -> CommonFilters:
        """延迟初始化 CommonFilters（需要窗口就绪后）。"""
        if self._filters is None:
            self._filters = CommonFilters(self._base.win, self._base.cam)
            self._initialized = True
        return self._filters

    # ── Bloom 泛光 ──
    def toggle_bloom(self) -> bool:
        """切换 Bloom 泛光。"""
        f = self._ensure_filters()
        self._bloom_enabled = not self._bloom_enabled
        if self._bloom_enabled:
            f.setBloom(
                blend=(0.3, 0.4, 0.3, 0.0),
                mintrigger=0.6,
                maxtrigger=1.0,
                desat=0.6,
                intensity=self._bloom_intensity,
                size=self._bloom_size,
            )
        else:
            f.delBloom()
        return self._bloom_enabled

    def set_bloom_intensity(self, intensity: float) -> None:
        """设置 Bloom 强度 (0.0 ~ 2.0)。"""
        self._bloom_intensity = max(0.0, min(2.0, intensity))
        if self._bloom_enabled:
            f = self._ensure_filters()
            f.setBloom(
                blend=(0.3, 0.4, 0.3, 0.0),
                mintrigger=0.6,
                maxtrigger=1.0,
                desat=0.6,
                intensity=self._bloom_intensity,
                size=self._bloom_size,
            )

    # ── 环境光遮蔽 AO ──
    def toggle_ao(self) -> bool:
        """切换环境光遮蔽。"""
        f = self._ensure_filters()
        self._ao_enabled = not self._ao_enabled
        if self._ao_enabled:
            f.setAmbientOcclusion(
                numsamples=16,
                radius=self._ao_radius,
                amount=self._ao_strength,
                strength=self._ao_strength,
                falloff=0.002,
            )
        else:
            f.delAmbientOcclusion()
        return self._ao_enabled

    # ── 模糊 ──
    def toggle_blur(self) -> bool:
        """切换模糊滤镜。"""
        f = self._ensure_filters()
        self._blur_enabled = not self._blur_enabled
        if self._blur_enabled:
            f.setBlurSharpen(self._blur_amount)
        else:
            f.delBlurSharpen()
        return self._blur_enabled

    def set_blur_amount(self, amount: float) -> None:
        """设置模糊程度 (0.0=最模糊, 1.0=正常, 2.0=锐化)。"""
        self._blur_amount = max(0.0, min(2.0, amount))
        if self._blur_enabled:
            f = self._ensure_filters()
            f.setBlurSharpen(self._blur_amount)

    # ── 反转颜色 ──
    def toggle_inverted(self) -> bool:
        """切换颜色反转。"""
        f = self._ensure_filters()
        self._inverted = not self._inverted
        if self._inverted:
            f.setInverted()
        else:
            f.delInverted()
        return self._inverted

    # ── HDR ──
    def toggle_hdr(self) -> bool:
        """切换 HDR 色调映射。"""
        f = self._ensure_filters()
        self._hdr_enabled = not self._hdr_enabled
        if self._hdr_enabled:
            f.setHighDynamicRange()
        else:
            f.delHighDynamicRange()
        return self._hdr_enabled

    # ── 全部关闭 ──
    def disable_all(self) -> None:
        """关闭所有后处理效果。"""
        if self._filters is None:
            return
        f = self._filters
        if self._bloom_enabled:
            f.delBloom()
            self._bloom_enabled = False
        if self._ao_enabled:
            f.delAmbientOcclusion()
            self._ao_enabled = False
        if self._blur_enabled:
            f.delBlurSharpen()
            self._blur_enabled = False
        if self._inverted:
            f.delInverted()
            self._inverted = False
        if self._hdr_enabled:
            f.delHighDynamicRange()
            self._hdr_enabled = False

    # ── 状态查询 ──
    @property
    def bloom_enabled(self) -> bool:
        return self._bloom_enabled

    @property
    def ao_enabled(self) -> bool:
        return self._ao_enabled

    @property
    def blur_enabled(self) -> bool:
        return self._blur_enabled

    @property
    def inverted_enabled(self) -> bool:
        return self._inverted

    @property
    def hdr_enabled(self) -> bool:
        return self._hdr_enabled
