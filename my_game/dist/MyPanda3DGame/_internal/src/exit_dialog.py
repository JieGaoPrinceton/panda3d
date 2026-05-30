"""
src/exit_dialog.py — ESC 退出确认对话框

按 ESC 弹出半透明遮罩 + 居中对话框，提供三个选项：
  - 存档并退出：先快速保存，再退出
  - 直接退出：不保存直接退出
  - 继续游戏：关闭对话框，恢复游戏
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Optional, Callable

from direct.gui.DirectGui import (
    DirectFrame,
    DirectButton,
    DirectLabel,
)

if TYPE_CHECKING:
    from direct.showbase.ShowBase import ShowBase


class ExitDialog:
    """ESC 退出确认对话框。"""

    def __init__(
        self,
        base: ShowBase,
        on_save: Optional[Callable] = None,
        on_resume: Optional[Callable] = None,
        cjk_font=None,
    ) -> None:
        self._base = base
        self._on_save = on_save      # 存档回调（save_load.quick_save）
        self._on_resume = on_resume  # 恢复游戏回调（game_fsm.toggle_pause 等）
        self._visible = False

        font_kwargs = {}
        if cjk_font:
            font_kwargs["text_font"] = cjk_font
        self._font_kwargs = font_kwargs

        self._build_dialog()

    def _build_dialog(self) -> None:
        """构建对话框 UI。"""

        # ── 半透明全屏遮罩 ──
        self._overlay = DirectFrame(
            frameColor=(0, 0, 0, 0.6),
            frameSize=(-2, 2, -2, 2),
            pos=(0, 0, 0),
            parent=self._base.aspect2d,
            sortOrder=100,
        )
        self._overlay.hide()

        # ── 居中对话框面板 ──
        self._panel = DirectFrame(
            frameColor=(0.08, 0.08, 0.15, 0.95),
            frameSize=(-0.5, 0.5, -0.35, 0.35),
            pos=(0, 0, 0),
            parent=self._overlay,
            relief="raised",
            borderWidth=(0.008, 0.008),
        )

        # ── 标题 ──
        DirectLabel(
            text="⚠ 退出游戏",
            text_scale=0.07,
            text_fg=(1, 0.85, 0.3, 1),
            text_shadow=(0, 0, 0, 0.8),
            frameColor=(0, 0, 0, 0),
            pos=(0, 0, 0.2),
            parent=self._panel,
            **self._font_kwargs,
        )

        # ── 提示文字 ──
        DirectLabel(
            text="确定要退出游戏吗？",
            text_scale=0.05,
            text_fg=(0.85, 0.85, 0.85, 1),
            frameColor=(0, 0, 0, 0),
            pos=(0, 0, 0.08),
            parent=self._panel,
            **self._font_kwargs,
        )

        # ── 按钮样式 ──
        btn_scale = 0.048
        btn_w = 0.18
        btn_h_half = 0.03

        # 存档并退出（绿色）
        DirectButton(
            text="💾 存档并退出",
            text_scale=btn_scale,
            text_fg=(1, 1, 1, 1),
            frameColor=(0.15, 0.45, 0.2, 1),
            relief="raised",
            borderWidth=(0.005, 0.005),
            frameSize=(-btn_w, btn_w, -btn_h_half, btn_h_half + 0.01),
            pos=(-0.25, 0, -0.08),
            parent=self._panel,
            command=self._on_save_and_exit,
            **self._font_kwargs,
        )

        # 直接退出（红色）
        DirectButton(
            text="🚪 直接退出",
            text_scale=btn_scale,
            text_fg=(1, 1, 1, 1),
            frameColor=(0.5, 0.15, 0.15, 1),
            relief="raised",
            borderWidth=(0.005, 0.005),
            frameSize=(-btn_w, btn_w, -btn_h_half, btn_h_half + 0.01),
            pos=(0.25, 0, -0.08),
            parent=self._panel,
            command=self._on_exit,
            **self._font_kwargs,
        )

        # 继续游戏（蓝色，居中下方）
        DirectButton(
            text="▶ 继续游戏",
            text_scale=btn_scale,
            text_fg=(1, 1, 1, 1),
            frameColor=(0.15, 0.25, 0.5, 1),
            relief="raised",
            borderWidth=(0.005, 0.005),
            frameSize=(-btn_w, btn_w, -btn_h_half, btn_h_half + 0.01),
            pos=(0, 0, -0.2),
            parent=self._panel,
            command=self._on_continue,
            **self._font_kwargs,
        )

    # ── 按钮回调 ──

    def _on_save_and_exit(self) -> None:
        """存档并退出。"""
        if self._on_save:
            self._on_save()
        sys.exit()

    def _on_exit(self) -> None:
        """直接退出。"""
        sys.exit()

    def _on_continue(self) -> None:
        """继续游戏：关闭对话框，恢复游戏状态。"""
        self.hide()
        if self._on_resume:
            self._on_resume()

    # ── 显示/隐藏 ──

    def show(self) -> None:
        """显示退出确认对话框。"""
        if self._visible:
            return
        self._visible = True
        self._overlay.show()

    def hide(self) -> None:
        """隐藏退出确认对话框。"""
        if not self._visible:
            return
        self._visible = False
        self._overlay.hide()

    def toggle(self) -> None:
        """切换对话框显示状态。"""
        if self._visible:
            self._on_continue()
        else:
            self.show()

    @property
    def is_visible(self) -> bool:
        """对话框是否可见。"""
        return self._visible
