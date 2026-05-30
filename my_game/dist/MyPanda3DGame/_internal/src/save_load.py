"""
src/save_load.py — 存档 / 读档系统
====================================
演示游戏状态持久化：
- JSON 格式存档
- F5 快速保存 / F9 快速加载
- 保存玩家位置、经验值、方块状态、时间

引擎对应: Python 标准库 json
"""

from __future__ import annotations

import json
import os
import time
from typing import TYPE_CHECKING, Optional, Dict, Any

from panda3d.core import Vec3

if TYPE_CHECKING:
    from direct.showbase.ShowBase import ShowBase
    from .player import PlayerController
    from .physics import PhysicsManager
    from .day_night import DayNightCycle


SAVE_DIR = "saves"
SAVE_FILE = "quicksave.json"


class SaveLoadManager:
    """存档 / 读档管理器。"""

    def __init__(self, base: ShowBase) -> None:
        self._base = base
        self._save_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            SAVE_DIR,
        )
        os.makedirs(self._save_dir, exist_ok=True)

        # 外部引用（由 main.py 设置）
        self._player: Optional[PlayerController] = None
        self._physics: Optional[PhysicsManager] = None
        self._day_night: Optional[DayNightCycle] = None

        # 状态提示回调
        self._on_message = None

    def setup(self, player=None, physics=None,
              day_night=None, on_message=None) -> None:
        """连接外部系统。"""
        self._player = player
        self._physics = physics
        self._day_night = day_night
        self._on_message = on_message

    def quick_save(self) -> bool:
        """
        F5 快速保存。

        Returns
        -------
        bool
            是否保存成功。
        """
        try:
            data = self._collect_state()
            path = os.path.join(self._save_dir, SAVE_FILE)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            if self._on_message:
                self._on_message("💾 已保存")
            return True
        except Exception as e:
            if self._on_message:
                self._on_message(f"❌ 保存失败: {e}")
            return False

    def quick_load(self) -> bool:
        """
        F9 快速加载。

        Returns
        -------
        bool
            是否加载成功。
        """
        path = os.path.join(self._save_dir, SAVE_FILE)
        if not os.path.isfile(path):
            if self._on_message:
                self._on_message("❌ 没有存档")
            return False

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._apply_state(data)

            if self._on_message:
                self._on_message("📂 已加载")
            return True
        except Exception as e:
            if self._on_message:
                self._on_message(f"❌ 加载失败: {e}")
            return False

    def _collect_state(self) -> Dict[str, Any]:
        """收集当前游戏状态。"""
        state: Dict[str, Any] = {
            "version": "0.6.0",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

        # 玩家状态
        if self._player:
            pos = self._player.physics_np.getPos()
            state["player"] = {
                "x": pos.getX(),
                "y": pos.getY(),
                "z": pos.getZ(),
                "exp": self._player.exp,
            }

        # 方块状态
        if self._physics:
            boxes = []
            for box_np in self._physics.spawned_boxes:
                if not box_np.isEmpty():
                    bp = box_np.getPos()
                    boxes.append({
                        "x": bp.getX(),
                        "y": bp.getY(),
                        "z": bp.getZ(),
                    })
            state["boxes"] = boxes

        # 日夜循环
        if self._day_night:
            state["day_night"] = {
                "time_of_day": self._day_night.time_of_day,
                "enabled": self._day_night.enabled,
            }

        return state

    def _apply_state(self, data: Dict[str, Any]) -> None:
        """应用存档状态。"""
        # 恢复玩家
        if self._player and "player" in data:
            p = data["player"]
            self._player.physics_np.setPos(p["x"], p["y"], p["z"])
            self._player.exp = p.get("exp", 0)
            # 唤醒物理体
            self._player.physics_np.node().setActive(True)
            self._player.physics_np.node().setLinearVelocity(Vec3(0, 0, 0))

        # 恢复方块（先清除现有方块，再重新生成）
        if self._physics and "boxes" in data:
            # 清除现有方块
            for box_np in list(self._physics.spawned_boxes):
                if not box_np.isEmpty():
                    self._physics.world.removeRigidBody(box_np.node())
                    box_np.removeNode()
            self._physics.spawned_boxes.clear()

            # 重新生成
            for box_data in data["boxes"]:
                pos = Vec3(box_data["x"], box_data["y"], box_data["z"])
                self._physics.spawn_box(pos)

        # 恢复日夜循环
        if self._day_night and "day_night" in data:
            dn = data["day_night"]
            self._day_night.set_time(dn.get("time_of_day", 0.25))
            if dn.get("enabled", False):
                self._day_night.enable()
            else:
                self._day_night.disable()

    def has_save(self) -> bool:
        """检查是否有存档。"""
        return os.path.isfile(os.path.join(self._save_dir, SAVE_FILE))

    def get_save_info(self) -> Optional[Dict[str, Any]]:
        """获取存档信息（不加载）。"""
        path = os.path.join(self._save_dir, SAVE_FILE)
        if not os.path.isfile(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {
                "timestamp": data.get("timestamp", "未知"),
                "version": data.get("version", "未知"),
                "exp": data.get("player", {}).get("exp", 0),
            }
        except Exception:
            return None
