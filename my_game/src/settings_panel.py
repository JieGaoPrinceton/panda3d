"""
src/settings_panel.py — 右上角设置按钮 + Tab 面板（调试 / 物理参数 / 快捷键）
"""

from __future__ import annotations

from typing import Dict, Optional, TYPE_CHECKING

from panda3d.core import TextNode, Vec3
from direct.gui.DirectGui import (
    DirectFrame,
    DirectSlider,
    DirectButton,
    DirectLabel,
)

from .constants import DEFAULTS

if TYPE_CHECKING:
    from direct.showbase.ShowBase import ShowBase
    from .physics import PhysicsManager
    from .player import PlayerController
    from .audio import AudioManager


class SettingsPanel:
    """右上角设置按钮 + 调试/物理参数 Tab 面板。"""

    def __init__(
        self,
        base: ShowBase,
        physics: PhysicsManager,
        player: PlayerController,
        audio: AudioManager,
        cjk_font=None,
    ) -> None:
        self._base = base
        self._physics = physics
        self._player = player
        self._audio = audio

        self._panel_visible = False
        self._current_tab = "physics"

        font_kwargs = {}
        if cjk_font:
            font_kwargs["text_font"] = cjk_font
        self._font_kwargs = font_kwargs

        self._build_settings_button()
        self._build_panel()

    # ── 右上角按钮 ──
    def _build_settings_button(self) -> None:
        self._settings_btn = DirectButton(
            text="⚙ 设置",
            text_scale=0.045,
            text_fg=(1, 1, 1, 1),
            frameColor=(0.2, 0.2, 0.35, 0.9),
            relief="raised",
            borderWidth=(0.005, 0.005),
            pos=(-0.12, 0, -0.38),
            parent=self._base.a2dTopRight,
            command=self.toggle,
            **self._font_kwargs,
        )

    # ── 主面板 ──
    def _build_panel(self) -> None:
        self._panel = DirectFrame(
            frameColor=(0.05, 0.05, 0.1, 0.92),
            frameSize=(-0.44, 0.44, -1.05, 0.55),
            pos=(1.18, 0, -0.1),
            parent=self._base.aspect2d,
        )
        self._panel.hide()

        self._build_tabs()
        self._build_debug_tab()
        self._build_physics_tab()
        self._build_hotkeys_tab()
        self._switch_tab("physics")

    # ── Tab 按钮（3 个标签：调试 / 物理参数 / 快捷键） ──
    def _build_tabs(self) -> None:
        tab_y = 0.48
        tab_w = 0.28  # 三等分宽度

        self._tab_btn_debug = DirectButton(
            text="🔍 调试",
            text_scale=0.04,
            text_fg=(1, 1, 1, 1),
            frameColor=(0.25, 0.25, 0.4, 1),
            relief="raised",
            borderWidth=(0.003, 0.003),
            frameSize=(-tab_w / 2, tab_w / 2, -0.03, 0.04),
            pos=(-tab_w, 0, tab_y),
            parent=self._panel,
            command=self._switch_tab,
            extraArgs=["debug"],
            **self._font_kwargs,
        )

        self._tab_btn_physics = DirectButton(
            text="⚡ 物理",
            text_scale=0.04,
            text_fg=(1, 1, 1, 1),
            frameColor=(0.15, 0.15, 0.25, 1),
            relief="raised",
            borderWidth=(0.003, 0.003),
            frameSize=(-tab_w / 2, tab_w / 2, -0.03, 0.04),
            pos=(0, 0, tab_y),
            parent=self._panel,
            command=self._switch_tab,
            extraArgs=["physics"],
            **self._font_kwargs,
        )

        self._tab_btn_hotkeys = DirectButton(
            text="⌨ 快捷键",
            text_scale=0.04,
            text_fg=(1, 1, 1, 1),
            frameColor=(0.15, 0.15, 0.25, 1),
            relief="raised",
            borderWidth=(0.003, 0.003),
            frameSize=(-tab_w / 2, tab_w / 2, -0.03, 0.04),
            pos=(tab_w, 0, tab_y),
            parent=self._panel,
            command=self._switch_tab,
            extraArgs=["hotkeys"],
            **self._font_kwargs,
        )

    # ── 调试 Tab ──
    def _build_debug_tab(self) -> None:
        self._debug_frame = DirectFrame(
            frameColor=(0, 0, 0, 0),
            frameSize=(-0.42, 0.42, -0.95, 0.42),
            pos=(0, 0, 0),
            parent=self._panel,
        )
        self._debug_frame.hide()

        y = 0.32
        DirectLabel(
            text="调试选项",
            text_scale=0.055,
            text_fg=(1, 0.9, 0.3, 1),
            text_shadow=(0, 0, 0, 0.8),
            frameColor=(0, 0, 0, 0),
            pos=(0, 0, y),
            parent=self._debug_frame,
            **self._font_kwargs,
        )

        debug_items = [
            ("碰撞体线框", self._toggle_wireframe, "_wireframe_btn"),
            ("包围盒显示", self._toggle_bbox, "_bbox_btn"),
            ("法线显示", self._toggle_normals, "_normals_btn"),
        ]

        for label_text, cmd, attr_name in debug_items:
            y -= 0.12
            DirectLabel(
                text=label_text,
                text_scale=0.042,
                text_fg=(0.9, 0.9, 0.9, 1),
                text_align=TextNode.ALeft,
                frameColor=(0, 0, 0, 0),
                pos=(-0.38, 0, y),
                parent=self._debug_frame,
                **self._font_kwargs,
            )
            btn = DirectButton(
                text="关闭",
                text_scale=0.04,
                text_fg=(1, 0.4, 0.4, 1),
                frameColor=(0.2, 0.15, 0.15, 1),
                relief="raised",
                borderWidth=(0.004, 0.004),
                frameSize=(-0.08, 0.08, -0.025, 0.035),
                pos=(0.28, 0, y),
                parent=self._debug_frame,
                command=cmd,
                **self._font_kwargs,
            )
            setattr(self, attr_name, btn)

        y -= 0.14
        DirectLabel(
            text="提示: 调试选项用于可视化\nBullet 物理碰撞体",
            text_scale=0.035,
            text_fg=(0.6, 0.6, 0.7, 1),
            text_align=TextNode.ACenter,
            frameColor=(0, 0, 0, 0),
            pos=(0, 0, y),
            parent=self._debug_frame,
            **self._font_kwargs,
        )

    # ── 物理参数 Tab ──
    def _build_physics_tab(self) -> None:
        self._physics_frame = DirectFrame(
            frameColor=(0, 0, 0, 0),
            frameSize=(-0.42, 0.42, -0.95, 0.42),
            pos=(0, 0, 0),
            parent=self._panel,
        )
        self._physics_frame.hide()

        y_start = 0.36
        y_step = 0.095
        slider_scale = 0.35

        DirectLabel(
            text="物理参数",
            text_scale=0.055,
            text_fg=(1, 0.9, 0.3, 1),
            text_shadow=(0, 0, 0, 0.8),
            frameColor=(0, 0, 0, 0),
            pos=(0, 0, y_start + 0.04),
            parent=self._physics_frame,
            **self._font_kwargs,
        )

        self._sliders: Dict[str, DirectSlider] = {}
        self._value_labels: Dict[str, DirectLabel] = {}

        slider_defs = [
            ("gravity",       "重力",       -30.0,  0.0,  DEFAULTS["gravity"]),
            ("player_mass",   "玩家质量",    0.5,  50.0,  DEFAULTS["player_mass"]),
            ("player_fric",   "玩家摩擦力",  0.0,   5.0,  DEFAULTS["player_friction"]),
            ("player_rest",   "玩家弹性",    0.0,   2.0,  DEFAULTS["player_restitution"]),
            ("jump_force",    "跳跃力度",    1.0,  20.0,  DEFAULTS["jump_force"]),
            ("box_mass",      "方块质量",    0.1,  20.0,  DEFAULTS["box_mass"]),
            ("box_fric",      "方块摩擦力",  0.0,   5.0,  DEFAULTS["box_friction"]),
            ("box_rest",      "方块弹性",    0.0,   2.0,  DEFAULTS["box_restitution"]),
            ("ground_fric",   "地面摩擦力",  0.0,   5.0,  DEFAULTS["ground_friction"]),
            ("ground_rest",   "地面弹性",    0.0,   2.0,  DEFAULTS["ground_restitution"]),
            ("sfx_volume",    "音效音量",    0.0,   1.0,  DEFAULTS["sfx_volume"]),
        ]

        for i, (key, label, vmin, vmax, default) in enumerate(slider_defs):
            y = y_start - (i + 1) * y_step

            DirectLabel(
                text=label,
                text_scale=0.038,
                text_fg=(0.9, 0.9, 0.9, 1),
                text_align=TextNode.ALeft,
                frameColor=(0, 0, 0, 0),
                pos=(-0.38, 0, y + 0.012),
                parent=self._physics_frame,
                **self._font_kwargs,
            )

            val_label = DirectLabel(
                text=f"{default:.2f}",
                text_scale=0.034,
                text_fg=(0.5, 1, 0.5, 1),
                text_align=TextNode.ARight,
                frameColor=(0, 0, 0, 0),
                pos=(0.38, 0, y + 0.012),
                parent=self._physics_frame,
            )
            self._value_labels[key] = val_label

            slider = DirectSlider(
                range=(vmin, vmax),
                value=default,
                pageSize=0.01,
                scale=slider_scale,
                pos=(0.02, 0, y - 0.022),
                parent=self._physics_frame,
                frameColor=(0.2, 0.2, 0.3, 1),
                thumb_frameColor=(0.4, 0.7, 1.0, 1),
                command=self._on_slider_change,
                extraArgs=[key],
            )
            self._sliders[key] = slider

        btn_y = y_start - (len(slider_defs) + 1) * y_step
        DirectButton(
            text="重置默认值",
            text_scale=0.045,
            text_fg=(1, 1, 1, 1),
            frameColor=(0.3, 0.15, 0.15, 1),
            relief="raised",
            pos=(0, 0, btn_y),
            scale=0.8,
            parent=self._physics_frame,
            command=self._reset_defaults,
            **self._font_kwargs,
        )

    # ── 快捷键 Tab ──
    def _build_hotkeys_tab(self) -> None:
        """构建快捷键说明标签页，列出所有游戏操作的按键绑定。"""
        self._hotkeys_frame = DirectFrame(
            frameColor=(0, 0, 0, 0),
            frameSize=(-0.42, 0.42, -0.95, 0.42),
            pos=(0, 0, 0),
            parent=self._panel,
        )
        self._hotkeys_frame.hide()

        y = 0.32
        DirectLabel(
            text="快捷键一览",
            text_scale=0.055,
            text_fg=(1, 0.9, 0.3, 1),
            text_shadow=(0, 0, 0, 0.8),
            frameColor=(0, 0, 0, 0),
            pos=(0, 0, y),
            parent=self._hotkeys_frame,
            **self._font_kwargs,
        )

        # ── 快捷键列表：(按键, 说明) ──
        hotkey_entries = [
            # 移动
            ("W / ↑",       "向前移动"),
            ("S / ↓",       "向后移动"),
            ("A / ←",       "向左移动"),
            ("D / →",       "向右移动"),
            ("Space",       "跳跃"),
            # 操作
            ("E",           "生成方块"),
            ("鼠标左键",     "拾取 / 收集"),
            ("X / Delete",  "删除选中方块"),
            ("V",           "切换视角模式"),
            ("鼠标右键拖拽",  "旋转相机"),
            ("滚轮",        "缩放距离 / FOV"),
            # 功能
            ("P",           "暂停 / 继续"),
            ("M",           "小地图开关"),
            ("N",           "NPC 开关"),
            ("T",           "加速时间"),
            # 系统
            ("F1",          "调试面板"),
            ("F2",          "物理参数面板"),
            ("F3",          "阴影开关"),
            ("F4",          "雾效开关"),
            ("F5",          "快速保存"),
            ("F6",          "天空盒开关"),
            ("F7",          "Bloom 开关"),
            ("F8",          "日夜循环开关"),
            ("F9",          "快速加载"),
            ("Esc",         "退出游戏"),
        ]

        row_h = 0.048  # 每行高度
        y -= 0.06      # 标题下方间距

        for key_text, desc_text in hotkey_entries:
            y -= row_h
            # 按键名（左侧，高亮色）
            DirectLabel(
                text=key_text,
                text_scale=0.034,
                text_fg=(0.5, 0.9, 1.0, 1),
                text_align=TextNode.ALeft,
                frameColor=(0, 0, 0, 0),
                pos=(-0.38, 0, y),
                parent=self._hotkeys_frame,
                **self._font_kwargs,
            )
            # 功能说明（右侧）
            DirectLabel(
                text=desc_text,
                text_scale=0.034,
                text_fg=(0.85, 0.85, 0.85, 1),
                text_align=TextNode.ALeft,
                frameColor=(0, 0, 0, 0),
                pos=(0.0, 0, y),
                parent=self._hotkeys_frame,
                **self._font_kwargs,
            )

    # ── Tab 切换 ──
    def _switch_tab(self, tab_name: str) -> None:
        self._current_tab = tab_name
        active = (0.25, 0.25, 0.45, 1)
        inactive = (0.12, 0.12, 0.2, 1)

        # 先全部隐藏 + 置灰
        self._debug_frame.hide()
        self._physics_frame.hide()
        self._hotkeys_frame.hide()
        self._tab_btn_debug["frameColor"] = inactive
        self._tab_btn_physics["frameColor"] = inactive
        self._tab_btn_hotkeys["frameColor"] = inactive

        # 激活选中的标签
        if tab_name == "debug":
            self._debug_frame.show()
            self._tab_btn_debug["frameColor"] = active
        elif tab_name == "physics":
            self._physics_frame.show()
            self._tab_btn_physics["frameColor"] = active
        elif tab_name == "hotkeys":
            self._hotkeys_frame.show()
            self._tab_btn_hotkeys["frameColor"] = active

    # ── 展开/收起 ──
    def toggle(self) -> None:
        self._panel_visible = not self._panel_visible
        if self._panel_visible:
            self._panel.show()
            self._settings_btn["text"] = "✕ 关闭"
        else:
            self._panel.hide()
            self._settings_btn["text"] = "⚙ 设置"

    def show_debug_tab(self) -> None:
        """F1 快捷键。"""
        if not self._panel_visible:
            self.toggle()
        self._switch_tab("debug")

    def show_physics_tab(self) -> None:
        """F2 快捷键。"""
        if not self._panel_visible:
            self.toggle()
        self._switch_tab("physics")

    def show_hotkeys_tab(self) -> None:
        """快捷键标签页。"""
        if not self._panel_visible:
            self.toggle()
        self._switch_tab("hotkeys")

    # ── 调试开关 ──
    def _set_btn_on(self, btn) -> None:
        btn["text"] = "开启"
        btn["text_fg"] = (0.4, 1, 0.4, 1)
        btn["frameColor"] = (0.15, 0.2, 0.15, 1)

    def _set_btn_off(self, btn) -> None:
        btn["text"] = "关闭"
        btn["text_fg"] = (1, 0.4, 0.4, 1)
        btn["frameColor"] = (0.2, 0.15, 0.15, 1)

    def _toggle_wireframe(self) -> None:
        pm = self._physics
        pm.debug_visible = not pm.debug_visible
        if pm.debug_visible:
            pm.debug_np.show()
            self._set_btn_on(self._wireframe_btn)
        else:
            pm.debug_np.hide()
            self._set_btn_off(self._wireframe_btn)

    def _toggle_bbox(self) -> None:
        debug_node = self._physics.debug_np.node()
        show = not (debug_node.isShowBoundingBoxes() if hasattr(debug_node, 'isShowBoundingBoxes') else False)
        debug_node.showBoundingBoxes(show)
        if show:
            self._set_btn_on(self._bbox_btn)
            if not self._physics.debug_visible:
                self._toggle_wireframe()
        else:
            self._set_btn_off(self._bbox_btn)

    def _toggle_normals(self) -> None:
        debug_node = self._physics.debug_np.node()
        show = not (debug_node.isShowNormals() if hasattr(debug_node, 'isShowNormals') else False)
        debug_node.showNormals(show)
        if show:
            self._set_btn_on(self._normals_btn)
            if not self._physics.debug_visible:
                self._toggle_wireframe()
        else:
            self._set_btn_off(self._normals_btn)

    # ── 物理滑块回调 ──
    def _on_slider_change(self, key: str = "") -> None:
        if not key or key not in self._sliders:
            return

        value = self._sliders[key]["value"]
        self._value_labels[key]["text"] = f"{value:.2f}"

        pm = self._physics
        pl = self._player

        if key == "gravity":
            pm.gravity = value
            pm.world.setGravity(Vec3(0, 0, value))
        elif key == "player_mass":
            pl.mass = value
            pl.physics_np.node().setMass(value)
        elif key == "player_fric":
            pl.friction = value
            pl.physics_np.node().setFriction(value)
        elif key == "player_rest":
            pl.restitution = value
            pl.physics_np.node().setRestitution(value)
        elif key == "jump_force":
            pl.jump_force = value
        elif key == "box_mass":
            pm.box_mass = value
            for box_np in pm.spawned_boxes:
                if not box_np.isEmpty():
                    box_np.node().setMass(value)
        elif key == "box_fric":
            pm.box_friction = value
            for box_np in pm.spawned_boxes:
                if not box_np.isEmpty():
                    box_np.node().setFriction(value)
        elif key == "box_rest":
            pm.box_restitution = value
            for box_np in pm.spawned_boxes:
                if not box_np.isEmpty():
                    box_np.node().setRestitution(value)
        elif key == "ground_fric":
            pm.ground_friction = value
            pm.ground_np.node().setFriction(value)
        elif key == "ground_rest":
            pm.ground_restitution = value
            pm.ground_np.node().setRestitution(value)
        elif key == "sfx_volume":
            self._audio.set_volume(value)

    def _reset_defaults(self) -> None:
        reset_map = {
            "gravity": DEFAULTS["gravity"],
            "player_mass": DEFAULTS["player_mass"],
            "player_fric": DEFAULTS["player_friction"],
            "player_rest": DEFAULTS["player_restitution"],
            "jump_force": DEFAULTS["jump_force"],
            "box_mass": DEFAULTS["box_mass"],
            "box_fric": DEFAULTS["box_friction"],
            "box_rest": DEFAULTS["box_restitution"],
            "ground_fric": DEFAULTS["ground_friction"],
            "ground_rest": DEFAULTS["ground_restitution"],
            "sfx_volume": DEFAULTS["sfx_volume"],
        }
        for key, val in reset_map.items():
            self._sliders[key]["value"] = val
            self._on_slider_change(key)
