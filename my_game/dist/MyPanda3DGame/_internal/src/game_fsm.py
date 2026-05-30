"""
src/game_fsm.py — 游戏状态机
==============================
演示 Panda3D 的 FSM (Finite State Machine)：
- Menu → Playing → Paused → GameOver
- 状态进入/退出回调
- 暂停菜单 UI

引擎对应: direct.fsm.FSM
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Optional

from panda3d.core import TextNode, Vec4
from direct.fsm.FSM import FSM
from direct.gui.DirectGui import (
    DirectFrame, DirectButton, DirectLabel,
)

if TYPE_CHECKING:
    from direct.showbase.ShowBase import ShowBase


class GameFSM(FSM):
    """
    游戏全局状态机。

    状态:
        Menu     — 主菜单
        Playing  — 游戏进行中
        Paused   — 暂停
        GameOver — 游戏结束
    """

    def __init__(self, base: ShowBase, cjk_font=None) -> None:
        FSM.__init__(self, "GameFSM")
        self._base = base
        self._font_kwargs = {}
        if cjk_font:
            self._font_kwargs["text_font"] = cjk_font

        # UI 容器
        self._menu_frame: Optional[DirectFrame] = None
        self._pause_frame: Optional[DirectFrame] = None
        self._gameover_frame: Optional[DirectFrame] = None

        # 游戏回调（由 main.py 设置）
        self._on_start_game = None
        self._on_resume_game = None
        self._on_pause_game = None

    def set_callbacks(self, on_start=None, on_resume=None,
                      on_pause=None) -> None:
        """设置状态切换回调。"""
        self._on_start_game = on_start
        self._on_resume_game = on_resume
        self._on_pause_game = on_pause

    # ══════════════════════════════════════
    # Menu 状态
    # ══════════════════════════════════════
    def enterMenu(self) -> None:
        """进入主菜单。"""
        self._menu_frame = DirectFrame(
            frameColor=(0.05, 0.05, 0.1, 0.95),
            frameSize=(-0.8, 0.8, -0.6, 0.6),
            pos=(0, 0, 0),
            parent=self._base.aspect2d,
        )

        DirectLabel(
            text="🎮 My Panda3D Game",
            text_scale=0.1,
            text_fg=(1, 0.9, 0.3, 1),
            text_shadow=(0, 0, 0, 0.8),
            frameColor=(0, 0, 0, 0),
            pos=(0, 0, 0.35),
            parent=self._menu_frame,
            **self._font_kwargs,
        )

        DirectLabel(
            text="Panda3D 引擎功能演示",
            text_scale=0.05,
            text_fg=(0.7, 0.7, 0.8, 1),
            frameColor=(0, 0, 0, 0),
            pos=(0, 0, 0.2),
            parent=self._menu_frame,
            **self._font_kwargs,
        )

        DirectButton(
            text="▶ 开始游戏",
            text_scale=0.06,
            text_fg=(1, 1, 1, 1),
            frameColor=(0.2, 0.5, 0.3, 1),
            relief="raised",
            borderWidth=(0.005, 0.005),
            frameSize=(-0.25, 0.25, -0.04, 0.05),
            pos=(0, 0, 0.0),
            parent=self._menu_frame,
            command=self._start_game,
            **self._font_kwargs,
        )

        DirectButton(
            text="✕ 退出",
            text_scale=0.05,
            text_fg=(1, 0.6, 0.6, 1),
            frameColor=(0.4, 0.15, 0.15, 1),
            relief="raised",
            borderWidth=(0.005, 0.005),
            frameSize=(-0.15, 0.15, -0.035, 0.045),
            pos=(0, 0, -0.15),
            parent=self._menu_frame,
            command=sys.exit,
            **self._font_kwargs,
        )

    def exitMenu(self) -> None:
        """离开主菜单。"""
        if self._menu_frame:
            self._menu_frame.destroy()
            self._menu_frame = None

    def _start_game(self) -> None:
        """开始游戏。"""
        self.request("Playing")

    # ══════════════════════════════════════
    # Playing 状态
    # ══════════════════════════════════════
    def enterPlaying(self) -> None:
        """进入游戏状态。"""
        if self._on_start_game:
            self._on_start_game()

    def exitPlaying(self) -> None:
        """离开游戏状态。"""
        pass

    # ══════════════════════════════════════
    # Paused 状态
    # ══════════════════════════════════════
    def enterPaused(self) -> None:
        """进入暂停状态。"""
        if self._on_pause_game:
            self._on_pause_game()

        self._pause_frame = DirectFrame(
            frameColor=(0.0, 0.0, 0.0, 0.7),
            frameSize=(-0.6, 0.6, -0.4, 0.4),
            pos=(0, 0, 0),
            parent=self._base.aspect2d,
        )

        DirectLabel(
            text="⏸ 游戏暂停",
            text_scale=0.08,
            text_fg=(1, 1, 0.3, 1),
            text_shadow=(0, 0, 0, 0.8),
            frameColor=(0, 0, 0, 0),
            pos=(0, 0, 0.2),
            parent=self._pause_frame,
            **self._font_kwargs,
        )

        DirectButton(
            text="▶ 继续游戏",
            text_scale=0.055,
            text_fg=(1, 1, 1, 1),
            frameColor=(0.2, 0.5, 0.3, 1),
            relief="raised",
            borderWidth=(0.005, 0.005),
            frameSize=(-0.2, 0.2, -0.035, 0.045),
            pos=(0, 0, 0.0),
            parent=self._pause_frame,
            command=self._resume_game,
            **self._font_kwargs,
        )

        DirectButton(
            text="🏠 主菜单",
            text_scale=0.05,
            text_fg=(0.8, 0.8, 1, 1),
            frameColor=(0.2, 0.2, 0.4, 1),
            relief="raised",
            borderWidth=(0.005, 0.005),
            frameSize=(-0.15, 0.15, -0.035, 0.045),
            pos=(0, 0, -0.12),
            parent=self._pause_frame,
            command=lambda: self.request("Menu"),
            **self._font_kwargs,
        )

        DirectButton(
            text="✕ 退出",
            text_scale=0.045,
            text_fg=(1, 0.5, 0.5, 1),
            frameColor=(0.3, 0.15, 0.15, 1),
            relief="raised",
            borderWidth=(0.005, 0.005),
            frameSize=(-0.12, 0.12, -0.03, 0.04),
            pos=(0, 0, -0.24),
            parent=self._pause_frame,
            command=sys.exit,
            **self._font_kwargs,
        )

    def exitPaused(self) -> None:
        """离开暂停状态。"""
        if self._pause_frame:
            self._pause_frame.destroy()
            self._pause_frame = None

    def _resume_game(self) -> None:
        """恢复游戏。"""
        if self._on_resume_game:
            self._on_resume_game()
        self.request("Playing")

    # ══════════════════════════════════════
    # GameOver 状态
    # ══════════════════════════════════════
    def enterGameOver(self) -> None:
        """进入游戏结束状态。"""
        self._gameover_frame = DirectFrame(
            frameColor=(0.1, 0.0, 0.0, 0.85),
            frameSize=(-0.7, 0.7, -0.4, 0.4),
            pos=(0, 0, 0),
            parent=self._base.aspect2d,
        )

        DirectLabel(
            text="💀 Game Over",
            text_scale=0.1,
            text_fg=(1, 0.3, 0.3, 1),
            text_shadow=(0, 0, 0, 0.8),
            frameColor=(0, 0, 0, 0),
            pos=(0, 0, 0.15),
            parent=self._gameover_frame,
            **self._font_kwargs,
        )

        DirectButton(
            text="🔄 重新开始",
            text_scale=0.055,
            text_fg=(1, 1, 1, 1),
            frameColor=(0.3, 0.5, 0.3, 1),
            relief="raised",
            borderWidth=(0.005, 0.005),
            frameSize=(-0.2, 0.2, -0.035, 0.045),
            pos=(0, 0, -0.05),
            parent=self._gameover_frame,
            command=lambda: self.request("Playing"),
            **self._font_kwargs,
        )

        DirectButton(
            text="✕ 退出",
            text_scale=0.045,
            text_fg=(1, 0.5, 0.5, 1),
            frameColor=(0.3, 0.15, 0.15, 1),
            relief="raised",
            borderWidth=(0.005, 0.005),
            frameSize=(-0.12, 0.12, -0.03, 0.04),
            pos=(0, 0, -0.2),
            parent=self._gameover_frame,
            command=sys.exit,
            **self._font_kwargs,
        )

    def exitGameOver(self) -> None:
        """离开游戏结束状态。"""
        if self._gameover_frame:
            self._gameover_frame.destroy()
            self._gameover_frame = None

    # ══════════════════════════════════════
    # 便捷方法
    # ══════════════════════════════════════
    def toggle_pause(self) -> None:
        """P 键切换暂停。"""
        if self.state == "Playing":
            self.request("Paused")
        elif self.state == "Paused":
            self._resume_game()
