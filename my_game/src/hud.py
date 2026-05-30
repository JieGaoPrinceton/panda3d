"""
src/hud.py — HUD 信息显示 + 中文字体加载
"""

from __future__ import annotations

import os
from typing import Optional, TYPE_CHECKING

from panda3d.core import DynamicTextFont, TextNode
from direct.gui.OnscreenText import OnscreenText

from .constants import CJK_FONT_CANDIDATES

if TYPE_CHECKING:
    from direct.showbase.ShowBase import ShowBase


def load_cjk_font() -> Optional[DynamicTextFont]:
    """尝试加载 macOS 系统中文字体。"""
    for path in CJK_FONT_CANDIDATES:
        if os.path.isfile(path):
            try:
                font = DynamicTextFont(path, 0)
                font.set_pixels_per_unit(64)
                return font
            except Exception:
                continue
    return None


class HUD:
    """左上角操作提示 + 右上角 FPS / 方块计数 / 地面状态。"""

    def __init__(self, base: ShowBase) -> None:
        self._base = base
        self.font = load_cjk_font()

        self._build_hints()
        self._build_status()

    def _build_hints(self) -> None:
        hints = [
            (0.00, "WASD: 移动  |  空格: 跳跃"),
            (0.06, "E: 生成方块  |  鼠标左键: 拾取"),
            (0.12, "Delete/X: 删除  |  V: 切换视角"),
            (0.18, "鼠标右键拖拽: 旋转视角  |  滚轮: 缩放"),
            (0.24, "F1: 调试  |  F2: 物理参数  |  ESC: 退出"),
        ]
        for y_off, text in hints:
            kwargs = dict(
                text=text, style=1,
                fg=(1, 1, 1, 1), shadow=(0, 0, 0, 0.6),
                scale=0.045, parent=self._base.a2dTopLeft,
                pos=(0.06, -y_off - 0.06), align=TextNode.ALeft,
            )
            if self.font:
                kwargs["font"] = self.font
            OnscreenText(**kwargs)

    def _build_status(self) -> None:
        def _make(text, fg, y):
            kw = dict(
                text=text, fg=fg,
                shadow=(0, 0, 0, 0.6), scale=0.05,
                parent=self._base.a2dTopRight,
                pos=(-0.06, y), align=TextNode.ARight,
            )
            if self.font:
                kw["font"] = self.font
            return OnscreenText(**kw)

        self.fps_text = _make("FPS: --", (0.4, 1, 0.4, 1), -0.06)
        self.box_text = _make("方块: 0", (1, 0.8, 0.2, 1), -0.14)
        self.ground_text = _make("", (0.3, 0.8, 1, 1), -0.22)
        self.exp_text = _make("经验: 0", (0.2, 1, 0.6, 1), -0.30)
        self.gem_text = _make("宝石: 0", (1, 0.6, 0.2, 1), -0.38)
        self.cam_text = _make("视角: 第三人称", (0.8, 0.6, 1, 1), -0.46)

        # 经验获取浮动提示（短暂显示后隐藏）
        kw_float = dict(
            text="", fg=(1, 1, 0.3, 1),
            shadow=(0, 0, 0, 0.8), scale=0.07,
            pos=(0, -0.3), mayChange=True,
        )
        if self.font:
            kw_float["font"] = self.font
        self.exp_float_text = OnscreenText(**kw_float)
        self.exp_float_text.hide()
        self._exp_float_timer = 0.0

    def show_exp_gain(self, amount: int) -> None:
        """显示经验获取浮动提示。"""
        self.exp_float_text.setText(f"+{amount} EXP ✨")
        self.exp_float_text.show()
        self._exp_float_timer = 1.5  # 显示 1.5 秒

    def update(self, fps: float, box_count: int, on_ground: bool,
               exp: int = 0, gem_count: int = 0, dt: float = 0.0,
               cam_mode: str = "第三人称") -> None:
        """每帧刷新 HUD 文字。"""
        self.fps_text.setText(f"FPS: {fps:.0f}")
        self.box_text.setText(f"方块: {box_count}")
        self.ground_text.setText("地面: ✓" if on_ground else "空中: ↑")
        self.exp_text.setText(f"经验: {exp}")
        self.gem_text.setText(f"宝石: {gem_count}")
        self.cam_text.setText(f"视角: {cam_mode}")

        # 浮动提示倒计时
        if self._exp_float_timer > 0:
            self._exp_float_timer -= dt
            if self._exp_float_timer <= 0:
                self.exp_float_text.hide()
