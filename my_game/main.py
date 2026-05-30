#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
my_game/main.py  —  Panda3D Mac 游戏开发模板（入口）
=====================================================
模块化架构：各子系统拆分到 src/ 包中。

运行方式:
    cd /Users/mac/code/panda3d-master/my_game
    python3 main.py
"""

from __future__ import annotations

import sys
from typing import Dict

from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from panda3d.core import WindowProperties, loadPrcFileData

# ── 初始化工作目录 & 配置 ──
import os as _os
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_os.chdir(_HERE)
loadPrcFileData("", open(_os.path.join(_HERE, "config.prc")).read())

# ── 子模块 ──
from src.physics import PhysicsManager
from src.player import PlayerController
from src.camera import OrbitCamera
from src.audio import AudioManager
from src.picking import PickingManager
from src.scene import SceneBuilder
from src.hud import HUD
from src.settings_panel import SettingsPanel
from src.collectibles import CollectibleManager


class MyGame(ShowBase):
    """游戏主类 — 组合各子系统。"""

    def __init__(self) -> None:
        super().__init__()

        # 窗口
        props = WindowProperties()
        props.setTitle("My Panda3D Game — Bullet + Jump + Audio + Pick + EXP")
        self.win.requestProperties(props)
        self.setBackgroundColor(0.1, 0.1, 0.15, 1)
        self.disableMouse()

        # 子系统初始化（顺序重要）
        self.physics = PhysicsManager(self)
        self.player = PlayerController(self, self.physics)
        self.orbit_cam = OrbitCamera(self)
        self.audio = AudioManager(self)
        self.picking = PickingManager(self, self.physics, self.audio)

        # 场景（地面模型 + 障碍物 + 光照）
        scene = SceneBuilder(self, self.physics)
        scene.build()

        # 可拾取经验方块系统
        self.collectibles = CollectibleManager(
            self, self.physics, self.player, self.audio,
        )

        # 连接拾取回调：点击经验方块时通过 PickingManager 转发
        self.picking.set_gem_collect_callback(self.collectibles.try_collect_by_name)

        # 初始相机
        self.camera.setPos(0, -20, 5)
        self.camera.lookAt(self.player.physics_np)

        # HUD
        self.hud = HUD(self)

        # 设置面板
        self.settings = SettingsPanel(
            self, self.physics, self.player, self.audio,
            cjk_font=self.hud.font,
        )

        # 输入绑定
        self._setup_input()

        # 主循环
        self.taskMgr.add(self._update, "update")

    # ══════════════════════════════════════════
    # 输入绑定
    # ══════════════════════════════════════════
    def _setup_input(self) -> None:
        self.keys: Dict[str, bool] = {
            "forward": False, "backward": False,
            "left": False, "right": False,
        }
        self.accept("escape", sys.exit)

        for key, action in [
            ("w", "forward"), ("arrow_up", "forward"),
            ("s", "backward"), ("arrow_down", "backward"),
            ("a", "left"), ("arrow_left", "left"),
            ("d", "right"), ("arrow_right", "right"),
        ]:
            self.accept(key, self._set_key, [action, True])
            self.accept(f"{key}-up", self._set_key, [action, False])

        # 空格 = 跳跃, E = 生成方块, V = 切换视角
        self.accept("space", self._on_jump)
        self.accept("e", self._on_spawn)
        self.accept("v", self.orbit_cam.cycle_mode)

        # 鼠标左键 = 拾取（普通方块选中 / 经验方块收集）
        self.accept("mouse1", self._on_pick)
        self.accept("delete", self.picking.delete_selected)
        self.accept("x", self.picking.delete_selected)

        # F1 / F2 = 设置面板 Tab 切换
        self.accept("f1", self.settings.show_debug_tab)
        self.accept("f2", self.settings.show_physics_tab)

        # 相机控制
        self.accept("mouse3", self.orbit_cam.on_mouse_press)
        self.accept("mouse3-up", self.orbit_cam.on_mouse_release)
        self.accept("wheel_up", self.orbit_cam.on_wheel_up)
        self.accept("wheel_down", self.orbit_cam.on_wheel_down)

    def _set_key(self, action: str, value: bool) -> None:
        self.keys[action] = value

    def _on_jump(self) -> None:
        if self.player.jump():
            self.audio.play("jump")

    def _on_spawn(self) -> None:
        pos = self.player.get_spawn_pos()
        self.physics.spawn_box(pos)
        self.audio.play("spawn")

    def _on_pick(self) -> None:
        """鼠标左键：拾取普通方块或收集经验方块。"""
        exp = self.picking.on_pick()
        if exp is not None and exp > 0:
            self.player.add_exp(exp)
            self.hud.show_exp_gain(exp)
            self.audio.play("pick")

    # ══════════════════════════════════════════
    # 主循环
    # ══════════════════════════════════════════
    def _update(self, task):
        dt = globalClock.get_dt()  # type: ignore[name-defined]

        # 玩家移动
        self.player.update(self.keys)

        # 物理步进
        self.physics.step(dt)

        # 可拾取方块更新（定时生成 + 自动拾取）
        collected_exp = self.collectibles.update(dt)
        if collected_exp is not None and collected_exp > 0:
            self.player.add_exp(collected_exp)
            self.hud.show_exp_gain(collected_exp)
            self.audio.play("pick")

        # 轨道相机
        self.orbit_cam.update(self.player.physics_np, self.player.floater)

        # HUD
        fps = globalClock.get_average_frame_rate()  # type: ignore[name-defined]
        self.hud.update(
            fps, self.physics.box_count, self.player.is_on_ground(),
            exp=self.player.exp,
            gem_count=self.collectibles.gem_count,
            dt=dt,
            cam_mode=self.orbit_cam.mode_name,
        )

        return Task.cont


# ──────────────────────────────────────────────
if __name__ == "__main__":
    game = MyGame()
    game.run()
