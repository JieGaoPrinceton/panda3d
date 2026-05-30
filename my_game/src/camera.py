"""
src/camera.py — 轨道相机控制
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from panda3d.core import NodePath

from .constants import (
    CAM_HEADING, CAM_PITCH, CAM_DISTANCE,
    CAM_PITCH_MIN, CAM_PITCH_MAX,
    CAM_DIST_MIN, CAM_DIST_MAX,
    CAM_MOUSE_SENSITIVITY,
)

if TYPE_CHECKING:
    from direct.showbase.ShowBase import ShowBase


class OrbitCamera:
    """鼠标右键拖拽旋转 + 滚轮缩放的轨道相机。"""

    def __init__(self, base: ShowBase) -> None:
        self._base = base

        self.heading = CAM_HEADING
        self.pitch = CAM_PITCH
        self.distance = CAM_DISTANCE
        self.sensitivity = CAM_MOUSE_SENSITIVITY

        self._dragging = False
        self._last_x = 0.0
        self._last_y = 0.0

    def on_mouse_press(self) -> None:
        self._dragging = True
        if self._base.mouseWatcherNode.hasMouse():
            md = self._base.mouseWatcherNode.getMouse()
            self._last_x = md.getX()
            self._last_y = md.getY()

    def on_mouse_release(self) -> None:
        self._dragging = False

    def on_wheel_up(self) -> None:
        self.distance = max(CAM_DIST_MIN, self.distance - 2.0)

    def on_wheel_down(self) -> None:
        self.distance = min(CAM_DIST_MAX, self.distance + 2.0)

    def update(self, target: NodePath, look_at: NodePath) -> None:
        """每帧更新相机位置。"""
        # 鼠标拖拽
        if self._dragging and self._base.mouseWatcherNode.hasMouse():
            md = self._base.mouseWatcherNode.getMouse()
            dx = md.getX() - self._last_x
            dy = md.getY() - self._last_y
            self._last_x = md.getX()
            self._last_y = md.getY()
            self.heading -= dx * self.sensitivity * 200
            self.pitch = max(
                CAM_PITCH_MIN,
                min(CAM_PITCH_MAX, self.pitch + dy * self.sensitivity * 200),
            )

        # 球坐标 → 笛卡尔坐标
        heading_rad = math.radians(self.heading)
        pitch_rad = math.radians(self.pitch)
        cam_x = target.getX() + self.distance * math.cos(pitch_rad) * math.sin(heading_rad)
        cam_y = target.getY() - self.distance * math.cos(pitch_rad) * math.cos(heading_rad)
        cam_z = target.getZ() + self.distance * math.sin(-pitch_rad) + 2.0
        self._base.camera.setPos(cam_x, cam_y, cam_z)
        self._base.camera.lookAt(look_at)
