"""
src/dialogue.py — NPC 对话框系统
=================================
屏幕底部弹出对话文本框，遇到 NPC 时随机生成中文对话。

引擎对应: DirectGUI · OnscreenText · DirectFrame
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Optional

from panda3d.core import TextNode, DynamicTextFont
from direct.gui.DirectGui import DirectFrame
from direct.gui.OnscreenText import OnscreenText

if TYPE_CHECKING:
    from direct.showbase.ShowBase import ShowBase


# 随机中文字符池（常用汉字）
_CHINESE_CHARS = (
    "你好世界今天气真不错啊我是守卫这里很危险请小心前方有怪物"
    "欢迎来到冒险之旅勇者快去拯救公主吧宝藏就在前面加油"
    "别靠近那个地方太黑暗了听说森林深处藏着古老的秘密"
    "需要帮助吗我可以给你指路这条道通往山顶风景非常美丽"
    "战斗开始准备好武器了吗敌人越来越强大我们必须团结一致"
    "休息一下吧旅途还很漫长记得补充体力和水分注意安全"
    "传说中的龙就住在那座火山里只有最勇敢的人才能打败它"
)


def _random_chinese(n: int = 20) -> str:
    """随机生成 *n* 个中文字符组成的句子。"""
    return "".join(random.choice(_CHINESE_CHARS) for _ in range(n))


class DialogueBox:
    """屏幕底部 NPC 对话框。

    Parameters
    ----------
    base : ShowBase
        Panda3D 应用实例。
    font : DynamicTextFont | None
        中文字体（可选，传入 HUD 已加载的字体）。
    """

    # 对话框自动隐藏时间（秒）
    DISPLAY_DURATION = 4.0

    def __init__(self, base: ShowBase,
                 font: Optional[DynamicTextFont] = None) -> None:
        self._base = base
        self._font = font
        self._visible = False
        self._timer = 0.0
        self._current_npc: Optional[str] = None

        # ── 底部半透明背景条 ──
        self._frame = DirectFrame(
            parent=base.aspect2d,
            frameColor=(0, 0, 0, 0.7),
            frameSize=(-1.8, 1.8, -0.18, 0.18),
            pos=(0, 0, -0.82),
        )

        # ── NPC 名称标签（左侧） ──
        name_kw = dict(
            text="", fg=(0.3, 1.0, 0.5, 1.0),
            shadow=(0, 0, 0, 0.8), scale=0.055,
            parent=self._frame,
            pos=(-1.7, 0.08), align=TextNode.ALeft,
            mayChange=True,
        )
        if self._font:
            name_kw["font"] = self._font
        self._name_text = OnscreenText(**name_kw)

        # ── 对话内容（居中偏左） ──
        body_kw = dict(
            text="", fg=(1, 1, 1, 1),
            shadow=(0, 0, 0, 0.6), scale=0.05,
            parent=self._frame,
            pos=(-1.7, -0.06), align=TextNode.ALeft,
            mayChange=True,
            wordwrap=60,
        )
        if self._font:
            body_kw["font"] = self._font
        self._body_text = OnscreenText(**body_kw)

        # 初始隐藏
        self._frame.hide()

    # ──────────────────────────────────────────
    # 公共 API
    # ──────────────────────────────────────────

    def show_dialogue(self, npc_name: str,
                      text: Optional[str] = None) -> None:
        """显示对话框。

        Parameters
        ----------
        npc_name : str
            NPC 名称。
        text : str | None
            对话内容。为 ``None`` 时随机生成 20 个中文字。
        """
        if text is None:
            text = _random_chinese(20)

        self._current_npc = npc_name
        self._name_text.setText(f"【{npc_name}】")
        self._body_text.setText(text)
        self._frame.show()
        self._visible = True
        self._timer = self.DISPLAY_DURATION

    def hide_dialogue(self) -> None:
        """立即隐藏对话框。"""
        self._frame.hide()
        self._visible = False
        self._current_npc = None

    def update(self, dt: float) -> None:
        """每帧更新（自动倒计时隐藏）。"""
        if not self._visible:
            return
        self._timer -= dt
        if self._timer <= 0:
            self.hide_dialogue()

    @property
    def is_visible(self) -> bool:
        return self._visible

    @property
    def current_npc(self) -> Optional[str]:
        return self._current_npc

    def cleanup(self) -> None:
        """清理 GUI 元素。"""
        self._frame.destroy()
