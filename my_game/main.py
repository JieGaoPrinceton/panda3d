#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
my_game/main.py  —  Panda3D Mac 游戏开发模板（入口）
=====================================================
模块化架构：各子系统拆分到 src/ 包中。

运行方式:
    cd /Users/mac/code/panda3d-master/my_game
    python3 main.py

架构概览:
    MyGame(ShowBase)
    ├── 核心系统:  physics / player / orbit_cam / audio / picking
    ├── 场景系统:  scene / collectibles
    ├── 视觉系统:  shadows / fog_mgr / skybox / post_fx / day_night
    ├── 游戏系统:  collision / npc_mgr / save_load / minimap / dialogue
    ├── UI 系统:   hud / settings / game_fsm
    └── 主循环:    _update()
"""

from __future__ import annotations

import sys
from typing import Dict

from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from panda3d.core import WindowProperties, loadPrcFileData

# ══════════════════════════════════════════════════════════════
# 初始化工作目录 & 加载 config.prc
# ══════════════════════════════════════════════════════════════
import os as _os

_HERE = _os.path.dirname(_os.path.abspath(__file__))
_os.chdir(_HERE)
loadPrcFileData("", open(_os.path.join(_HERE, "config.prc")).read())

# ══════════════════════════════════════════════════════════════
# 子模块导入
# ══════════════════════════════════════════════════════════════

# ── 核心系统 ──
from src.physics import PhysicsManager          # Bullet 物理引擎
from src.player import PlayerController          # 玩家控制器
from src.camera import OrbitCamera               # 多模式相机
from src.audio import AudioManager               # 音效管理
from src.picking import PickingManager           # 鼠标射线拾取

# ── 场景系统 ──
from src.scene import SceneBuilder               # 场景构建（地面+障碍物+光照）
from src.collectibles import CollectibleManager  # 可拾取经验方块

# ── 视觉系统 ──
from src.shadows import ShadowManager            # 阴影渲染
from src.fog import FogManager                   # 雾效
from src.skybox import SkyBox                    # 程序化天空盒
from src.post_processing import PostProcessing   # 后处理滤镜
from src.day_night import DayNightCycle          # 日夜循环

# ── 游戏系统 ──
from src.collision import CollisionManager       # Panda3D 原生碰撞
from src.npc import NPCManager                  # NPC / AI 巡逻
from src.save_load import SaveLoadManager        # 存档 / 读档
from src.minimap import MiniMap                  # 小地图
from src.dialogue import DialogueBox             # NPC 对话框
from src.exit_dialog import ExitDialog           # ESC 退出确认对话框

# ── UI 系统 ──
from src.hud import HUD                         # HUD 信息显示
from src.settings_panel import SettingsPanel     # 设置面板
from src.game_fsm import GameFSM                # 游戏状态机
from src.animations import AnimationManager      # Interval 动画


class MyGame(ShowBase):
    """游戏主类 — 组合各子系统。

    职责:
        1. 初始化所有子系统（顺序重要，有依赖关系）
        2. 绑定键盘/鼠标输入
        3. 驱动主循环 ``_update()``
    """

    def __init__(self) -> None:
        super().__init__()

        # ── 窗口配置 ──
        props = WindowProperties()
        props.setTitle("My Panda3D Game — 全功能演示 v0.6.0")
        self.win.requestProperties(props)
        self.setBackgroundColor(0.1, 0.1, 0.15, 1)
        self.disableMouse()  # 禁用默认鼠标控制，使用自定义相机

        # ══════════════════════════════════════════
        # 1. 核心系统初始化（顺序重要）
        # ══════════════════════════════════════════
        self.physics = PhysicsManager(self)
        self.player = PlayerController(self, self.physics)
        self.orbit_cam = OrbitCamera(self)
        self.audio = AudioManager(self)
        self.picking = PickingManager(self, self.physics, self.audio)

        # ══════════════════════════════════════════
        # 2. 场景系统
        # ══════════════════════════════════════════
        self.scene = SceneBuilder(self, self.physics)
        self.scene.build()  # 加载地面模型 + 静态障碍物 + 光照

        self.collectibles = CollectibleManager(
            self, self.physics, self.player, self.audio,
        )
        # 连接鼠标拾取 → 经验方块收集的回调
        self.picking.set_gem_collect_callback(self.collectibles.try_collect_by_name)

        # ══════════════════════════════════════════
        # 3. 视觉系统（依赖场景中的 sun_np）
        # ══════════════════════════════════════════
        self.shadows = ShadowManager(self)
        if self.scene.sun_np:
            self.shadows.setup_shadow_light(self.scene.sun_np)

        self.fog_mgr = FogManager(self)
        self.skybox = SkyBox(self)
        self.anim = AnimationManager(self)
        self.post_fx = PostProcessing(self)

        self.day_night = DayNightCycle(self)
        if self.scene.sun_np:
            self.day_night.setup(
                self.scene.sun_np,
                skybox=self.skybox,
                fog=self.fog_mgr,
            )

        # ══════════════════════════════════════════
        # 4. 游戏系统
        # ══════════════════════════════════════════
        self.collision = CollisionManager(self)
        self.collision.setup_player_collider(self.player.physics_np)
        self.collision.create_demo_triggers()

        self.npc_mgr = NPCManager(self)
        self.npc_mgr.spawn_default_npcs()

        self.save_load = SaveLoadManager(self)
        self.save_load.setup(
            player=self.player,
            physics=self.physics,
            day_night=self.day_night,
            on_message=self._show_system_message,
        )

        self.minimap = MiniMap(self)
        self.dialogue = DialogueBox(self, font=None)  # 字体在 HUD 之后设置

        # ══════════════════════════════════════════
        # 5. UI 系统（依赖 HUD 的中文字体）
        # ══════════════════════════════════════════
        # 初始相机位置
        self.camera.setPos(0, -20, 5)
        self.camera.lookAt(self.player.physics_np)

        self.hud = HUD(self)

        # 将 HUD 加载的中文字体传给对话框
        self.dialogue._font = self.hud.font
        if self.hud.font:
            self.dialogue._name_text.setFont(self.hud.font)
            self.dialogue._body_text.setFont(self.hud.font)

        self.game_fsm = GameFSM(self, cjk_font=self.hud.font)
        self.game_fsm.set_callbacks(
            on_start=self._on_game_start,
            on_resume=self._on_game_resume,
            on_pause=self._on_game_pause,
        )

        self.settings = SettingsPanel(
            self, self.physics, self.player, self.audio,
            cjk_font=self.hud.font,
        )

        # ESC 退出确认对话框
        self.exit_dialog = ExitDialog(
            self,
            on_save=self.save_load.quick_save,
            on_resume=self._on_exit_dialog_resume,
            cjk_font=self.hud.font,
        )

        # ══════════════════════════════════════════
        # 6. 输入绑定 & 启动
        # ══════════════════════════════════════════
        self._setup_input()
        self.taskMgr.add(self._update, "update")

        # 直接进入游戏（跳过菜单，可改为 self.game_fsm.request("Menu")）
        self.game_fsm.request("Playing")

    # ══════════════════════════════════════════════════════════════
    # 系统消息
    # ══════════════════════════════════════════════════════════════

    def _show_system_message(self, msg: str) -> None:
        """在 HUD 上显示系统消息（复用浮动提示文本）。"""
        if hasattr(self, 'hud'):
            self.hud.show_exp_gain(0)
            self.hud.exp_float_text.setText(msg)
            self.hud.exp_float_text.show()
            self.hud._exp_float_timer = 2.0

    # ══════════════════════════════════════════════════════════════
    # FSM 回调（状态切换时触发）
    # ══════════════════════════════════════════════════════════════

    def _on_game_start(self) -> None:
        """从菜单进入游戏时触发。"""
        pass

    def _on_game_resume(self) -> None:
        """从暂停恢复游戏时触发。"""
        pass

    def _on_game_pause(self) -> None:
        """暂停游戏时触发。"""
        pass

    # ══════════════════════════════════════════════════════════════
    # 输入绑定
    # ══════════════════════════════════════════════════════════════

    def _setup_input(self) -> None:
        """绑定所有键盘/鼠标输入。"""

        # ── 移动键状态 ──
        self.keys: Dict[str, bool] = {
            "forward": False, "backward": False,
            "left": False, "right": False,
        }
        self.accept("escape", self._on_escape)

        # WASD / 方向键 → 移动
        for key, action in [
            ("w", "forward"), ("arrow_up", "forward"),
            ("s", "backward"), ("arrow_down", "backward"),
            ("a", "left"), ("arrow_left", "left"),
            ("d", "right"), ("arrow_right", "right"),
        ]:
            self.accept(key, self._set_key, [action, True])
            self.accept(f"{key}-up", self._set_key, [action, False])

        # ── 基础操作 ──
        self.accept("space", self._on_jump)           # 跳跃
        self.accept("e", self._on_spawn)               # 生成方块
        self.accept("v", self.orbit_cam.cycle_mode)    # 切换视角

        # ── 鼠标操作 ──
        self.accept("mouse1", self._on_pick)           # 左键拾取
        self.accept("delete", self.picking.delete_selected)
        self.accept("x", self.picking.delete_selected)

        # ── 设置面板 ──
        self.accept("f1", self.settings.show_debug_tab)
        self.accept("f2", self.settings.show_physics_tab)

        # ── 相机控制 ──
        self.accept("mouse3", self.orbit_cam.on_mouse_press)
        self.accept("mouse3-up", self.orbit_cam.on_mouse_release)
        self.accept("wheel_up", self.orbit_cam.on_wheel_up)
        self.accept("wheel_down", self.orbit_cam.on_wheel_down)

        # ── 功能快捷键 ──
        self.accept("p", self.game_fsm.toggle_pause)   # 暂停
        self.accept("f5", self.save_load.quick_save)    # 快速保存
        self.accept("f9", self.save_load.quick_load)    # 快速加载
        self.accept("f3", self._toggle_shadows)         # 阴影
        self.accept("f4", self._toggle_fog)             # 雾效
        self.accept("f6", self._toggle_skybox)          # 天空盒
        self.accept("f7", self._toggle_bloom)           # Bloom
        self.accept("f8", self._toggle_day_night)       # 日夜循环
        self.accept("m", self._toggle_minimap)          # 小地图
        self.accept("n", self._toggle_npc)              # NPC
        self.accept("t", self._speed_up_time)           # 加速时间

    def _on_escape(self) -> None:
        """ESC 键：弹出退出确认对话框（再按 ESC 关闭）。"""
        self.exit_dialog.toggle()
        # 弹出对话框时暂停游戏
        if self.exit_dialog.is_visible:
            if self.game_fsm.state == "Playing":
                self.game_fsm.toggle_pause()
        # 注意：关闭对话框时由 _on_exit_dialog_resume 恢复

    def _on_exit_dialog_resume(self) -> None:
        """退出对话框选择"继续游戏"时的回调。"""
        if self.game_fsm.state == "Paused":
            self.game_fsm.toggle_pause()

    def _set_key(self, action: str, value: bool) -> None:
        self.keys[action] = value

    # ══════════════════════════════════════════════════════════════
    # 操作回调
    # ══════════════════════════════════════════════════════════════

    def _on_jump(self) -> None:
        """空格键：跳跃（仅 Playing 状态）。"""
        if self.game_fsm.state != "Playing":
            return
        if self.player.jump():
            self.audio.play("jump")

    def _on_spawn(self) -> None:
        """E 键：在玩家前方生成方块（仅 Playing 状态）。"""
        if self.game_fsm.state != "Playing":
            return
        pos = self.player.get_spawn_pos()
        box_np = self.physics.spawn_box(pos)
        self.audio.play("spawn")
        if box_np:
            self.anim.spawn_bounce(box_np)

    def _on_pick(self) -> None:
        """鼠标左键：拾取普通方块或收集经验方块。"""
        if self.game_fsm.state != "Playing":
            return
        exp = self.picking.on_pick()
        if exp is not None and exp > 0:
            self.player.add_exp(exp)
            self.hud.show_exp_gain(exp)
            self.audio.play("pick")

    # ══════════════════════════════════════════════════════════════
    # 功能切换（快捷键回调）
    # ══════════════════════════════════════════════════════════════

    def _toggle_shadows(self) -> None:
        on = self.shadows.toggle_shadows()
        self._show_system_message(f"阴影: {'开启' if on else '关闭'}")

    def _toggle_fog(self) -> None:
        on = self.fog_mgr.toggle()
        self._show_system_message(f"雾效: {'开启' if on else '关闭'}")

    def _toggle_skybox(self) -> None:
        on = self.skybox.toggle()
        self._show_system_message(f"天空盒: {'开启' if on else '关闭'}")

    def _toggle_bloom(self) -> None:
        on = self.post_fx.toggle_bloom()
        self._show_system_message(f"Bloom: {'开启' if on else '关闭'}")

    def _toggle_day_night(self) -> None:
        on = self.day_night.toggle()
        self._show_system_message(f"日夜循环: {'开启' if on else '关闭'}")

    def _toggle_minimap(self) -> None:
        on = self.minimap.toggle()
        self._show_system_message(f"小地图: {'开启' if on else '关闭'}")

    def _toggle_npc(self) -> None:
        on = self.npc_mgr.toggle()
        self._show_system_message(f"NPC: {'开启' if on else '关闭'}")

    def _speed_up_time(self) -> None:
        """T 键：循环切换时间倍速 1x → 2x → 5x → 10x → 1x。"""
        speeds = [1.0, 2.0, 5.0, 10.0]
        current = getattr(self, '_time_speed_idx', 0)
        current = (current + 1) % len(speeds)
        self._time_speed_idx = current
        self.day_night.set_time_speed(speeds[current])
        self._show_system_message(f"时间倍速: {speeds[current]:.0f}x")

    # ══════════════════════════════════════════════════════════════
    # 主循环
    # ══════════════════════════════════════════════════════════════

    def _update(self, task):
        """每帧更新所有子系统。

        更新顺序:
            1. 玩家移动（WASD 跟随相机朝向）
            2. 物理步进
            3. 可拾取方块（定时生成 + 自动拾取）
            4. 碰撞检测（Panda3D 原生触发区域）
            5. NPC 更新 + 对话触发
            6. 对话框倒计时
            7. 日夜循环
            8. 小地图
            9. 相机跟随（暂停时也更新）
            10. HUD 刷新
        """
        dt = globalClock.get_dt()  # type: ignore[name-defined]

        # ── 仅在 Playing 状态更新游戏逻辑 ──
        if self.game_fsm.state == "Playing":
            # 1. 玩家移动（WASD 方向跟随相机 heading）
            self.player.update(self.keys, self.orbit_cam.current_heading)

            # 2. 物理步进（Bullet 引擎）
            self.physics.step(dt)

            # 3. 可拾取方块（定时生成 + 自动拾取检测）
            collected_exp = self.collectibles.update(dt)
            if collected_exp is not None and collected_exp > 0:
                self.player.add_exp(collected_exp)
                self.hud.show_exp_gain(collected_exp)
                self.audio.play("pick")

            # 4. 碰撞检测（Panda3D 原生触发区域）
            self.collision.update()

            # 5. NPC 更新 + 对话触发
            npc_trigger = self.npc_mgr.update(dt, self.player.physics_np.getPos())
            if npc_trigger is not None:
                self.dialogue.show_dialogue(npc_trigger)

            # 6. 对话框自动隐藏倒计时
            self.dialogue.update(dt)

            # 7. 日夜循环（太阳旋转 + 颜色插值）
            self.day_night.update(dt)

            # 8. 小地图（跟随玩家位置）
            self.minimap.update(self.player.physics_np.getPos())

        # ── 以下在所有状态都更新 ──

        # 9. 轨道相机（暂停时也允许旋转视角）
        self.orbit_cam.update(self.player.physics_np, self.player.floater)

        # 10. HUD 信息刷新
        fps = globalClock.get_average_frame_rate()  # type: ignore[name-defined]
        self.hud.update(
            fps, self.physics.box_count, self.player.is_on_ground(),
            exp=self.player.exp,
            gem_count=self.collectibles.gem_count,
            dt=dt,
            cam_mode=self.orbit_cam.mode_name,
        )

        return Task.cont


# ══════════════════════════════════════════════════════════════
# 入口
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    game = MyGame()
    game.run()
