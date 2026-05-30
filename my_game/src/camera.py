"""
src/camera.py — 多模式相机控制
================================
三种模式:
    - 第三人称: 相机在玩家身后上方，右键拖拽旋转，滚轮调距离
    - 第一人称: 相机在玩家头部，右键拖拽看向，滚轮调 FOV
    - 轨道相机: 自由旋转 + 滚轮缩放

V 键循环切换模式。

引擎对应: panda3d.core.Camera · 手动三角函数计算
"""

from __future__ import annotations

import math
from enum import Enum
from typing import TYPE_CHECKING

from panda3d.core import NodePath, Vec3

from .constants import (
    CAM_HEADING, CAM_PITCH, CAM_DISTANCE,
    CAM_PITCH_MIN, CAM_PITCH_MAX,
    CAM_DIST_MIN, CAM_DIST_MAX,
    CAM_MOUSE_SENSITIVITY,
)

if TYPE_CHECKING:
    from direct.showbase.ShowBase import ShowBase


class CameraMode(Enum):
    """相机模式枚举。"""
    THIRD_PERSON = "第三人称"
    FIRST_PERSON = "第一人称"
    ORBIT = "轨道相机"


class OrbitCamera:
    """多模式相机控制器。

    核心数学:
        相机位置通过球坐标系计算:
        x = target.x + distance * cos(pitch) * sin(heading)
        y = target.y - distance * cos(pitch) * cos(heading)
        z = target.z + distance * sin(-pitch) + offset

    Attributes
    ----------
    mode : CameraMode
        当前相机模式。
    heading : float
        轨道模式的水平旋转角（度）。
    pitch : float
        轨道模式的垂直旋转角（度）。
    distance : float
        轨道模式的相机距离。
    """

    # 第三人称参数
    TP_OFFSET_UP = 3.0       # 相机在玩家上方的高度偏移
    TP_OFFSET_BACK = 10.0    # 相机在玩家身后的距离

    # 第一人称参数
    FP_EYE_HEIGHT = 1.2      # 眼睛高度（相对玩家物理体中心）

    def __init__(self, base: ShowBase) -> None:
        self._base = base

        # 轨道模式参数
        self.heading = CAM_HEADING
        self.pitch = CAM_PITCH
        self.distance = CAM_DISTANCE
        self.sensitivity = CAM_MOUSE_SENSITIVITY

        # 鼠标拖拽状态
        self._dragging = False
        self._last_x = 0.0
        self._last_y = 0.0

        # 当前模式
        self.mode = CameraMode.THIRD_PERSON

        # 第三人称独立 heading/pitch
        self._tp_heading = 180.0
        self._tp_pitch = -15.0

        # 第一人称独立 heading/pitch
        self._fp_heading = 180.0
        self._fp_pitch = 0.0

        # 第一人称 FOV（视野角度，滚轮可调）
        self._fp_fov = 60.0
        self._fp_fov_default = 60.0

    # ──────────────────────────────────────────────────────────
    # 属性
    # ──────────────────────────────────────────────────────────

    @property
    def mode_name(self) -> str:
        """返回当前模式的中文名称（用于 HUD 显示）。"""
        return self.mode.value

    @property
    def current_heading(self) -> float:
        """返回当前模式的 heading 角度（度）。

        用于 PlayerController.update() 将 WASD 输入旋转到相机坐标系。
        """
        if self.mode == CameraMode.THIRD_PERSON:
            return self._tp_heading
        elif self.mode == CameraMode.FIRST_PERSON:
            return self._fp_heading
        else:  # ORBIT
            return self.heading

    # ──────────────────────────────────────────────────────────
    # 模式切换
    # ──────────────────────────────────────────────────────────

    def cycle_mode(self) -> None:
        """V 键：循环切换 第三人称 → 第一人称 → 轨道 → 第三人称。"""
        # 离开第一人称时恢复默认 FOV
        if self.mode == CameraMode.FIRST_PERSON:
            self._fp_fov = self._fp_fov_default
            self._base.camLens.setFov(self._fp_fov_default)

        modes = list(CameraMode)
        idx = modes.index(self.mode)
        self.mode = modes[(idx + 1) % len(modes)]

    # ──────────────────────────────────────────────────────────
    # 鼠标输入
    # ──────────────────────────────────────────────────────────

    def on_mouse_press(self) -> None:
        """右键按下：开始拖拽旋转。"""
        self._dragging = True
        if self._base.mouseWatcherNode.hasMouse():
            md = self._base.mouseWatcherNode.getMouse()
            self._last_x = md.getX()
            self._last_y = md.getY()

    def on_mouse_release(self) -> None:
        """右键释放：停止拖拽。"""
        self._dragging = False

    def on_wheel_up(self) -> None:
        """滚轮上滑：缩小距离 / 缩小 FOV。"""
        if self.mode == CameraMode.ORBIT:
            self.distance = max(CAM_DIST_MIN, self.distance - 2.0)
        elif self.mode == CameraMode.THIRD_PERSON:
            self.TP_OFFSET_BACK = max(3.0, self.TP_OFFSET_BACK - 1.0)
        elif self.mode == CameraMode.FIRST_PERSON:
            # 缩小 FOV = 放大（望远镜效果），范围 20°–120°
            self._fp_fov = max(20.0, self._fp_fov - 5.0)
            self._base.camLens.setFov(self._fp_fov)

    def on_wheel_down(self) -> None:
        """滚轮下滑：增大距离 / 增大 FOV。"""
        if self.mode == CameraMode.ORBIT:
            self.distance = min(CAM_DIST_MAX, self.distance + 2.0)
        elif self.mode == CameraMode.THIRD_PERSON:
            self.TP_OFFSET_BACK = min(30.0, self.TP_OFFSET_BACK + 1.0)
        elif self.mode == CameraMode.FIRST_PERSON:
            # 增大 FOV = 广角效果
            self._fp_fov = min(120.0, self._fp_fov + 5.0)
            self._base.camLens.setFov(self._fp_fov)

    def _handle_mouse_drag(self) -> tuple[float, float]:
        """处理鼠标拖拽，返回帧间位移 (dx, dy)。"""
        if not self._dragging or not self._base.mouseWatcherNode.hasMouse():
            return 0.0, 0.0
        md = self._base.mouseWatcherNode.getMouse()
        dx = md.getX() - self._last_x
        dy = md.getY() - self._last_y
        self._last_x = md.getX()
        self._last_y = md.getY()
        return dx, dy

    # ──────────────────────────────────────────────────────────
    # 每帧更新（根据模式分发）
    # ──────────────────────────────────────────────────────────

    def update(self, target: NodePath, look_at: NodePath) -> None:
        """每帧更新相机位置。

        Parameters
        ----------
        target : NodePath
            跟随目标（玩家物理体节点）。
        look_at : NodePath
            注视目标（玩家头顶 floater 节点）。
        """
        if self.mode == CameraMode.ORBIT:
            self._update_orbit(target, look_at)
        elif self.mode == CameraMode.THIRD_PERSON:
            self._update_third_person(target)
        elif self.mode == CameraMode.FIRST_PERSON:
            self._update_first_person(target)

    def _update_orbit(self, target: NodePath, look_at: NodePath) -> None:
        """轨道相机：围绕目标自由旋转。

        球坐标系公式:
            cam_x = target.x + dist * cos(pitch) * sin(heading)
            cam_y = target.y - dist * cos(pitch) * cos(heading)
            cam_z = target.z + dist * sin(-pitch) + 2.0
        """
        dx, dy = self._handle_mouse_drag()
        if dx or dy:
            self.heading -= dx * self.sensitivity * 200
            self.pitch = max(
                CAM_PITCH_MIN,
                min(CAM_PITCH_MAX, self.pitch + dy * self.sensitivity * 200),
            )

        heading_rad = math.radians(self.heading)
        pitch_rad = math.radians(self.pitch)
        cam_x = target.getX() + self.distance * math.cos(pitch_rad) * math.sin(heading_rad)
        cam_y = target.getY() - self.distance * math.cos(pitch_rad) * math.cos(heading_rad)
        cam_z = target.getZ() + self.distance * math.sin(-pitch_rad) + 2.0
        self._base.camera.setPos(cam_x, cam_y, cam_z)
        self._base.camera.lookAt(look_at)

    def _update_third_person(self, target: NodePath) -> None:
        """第三人称：相机在玩家身后上方，右键拖拽旋转视角。

        与轨道模式类似，但使用独立的 heading/pitch 和固定偏移距离。
        """
        dx, dy = self._handle_mouse_drag()
        if dx or dy:
            self._tp_heading -= dx * self.sensitivity * 200
            self._tp_pitch = max(
                -60.0,
                min(20.0, self._tp_pitch + dy * self.sensitivity * 200),
            )

        heading_rad = math.radians(self._tp_heading)
        pitch_rad = math.radians(self._tp_pitch)

        cam_x = target.getX() + self.TP_OFFSET_BACK * math.cos(pitch_rad) * math.sin(heading_rad)
        cam_y = target.getY() - self.TP_OFFSET_BACK * math.cos(pitch_rad) * math.cos(heading_rad)
        cam_z = target.getZ() + self.TP_OFFSET_BACK * math.sin(-pitch_rad) + self.TP_OFFSET_UP

        self._base.camera.setPos(cam_x, cam_y, cam_z)
        self._base.camera.lookAt(
            target.getX(), target.getY(), target.getZ() + 1.0,
        )

    def _update_first_person(self, target: NodePath) -> None:
        """第一人称：相机在玩家头部，右键拖拽控制视线方向。

        视线方向通过 heading/pitch 计算前方注视点:
            look_x = cam_x + dist * cos(pitch) * sin(heading)
            look_y = cam_y - dist * cos(pitch) * cos(heading)
            look_z = cam_z + dist * sin(pitch)
        """
        dx, dy = self._handle_mouse_drag()
        if dx or dy:
            self._fp_heading -= dx * self.sensitivity * 200
            self._fp_pitch = max(
                -80.0,
                min(60.0, self._fp_pitch + dy * self.sensitivity * 200),
            )

        # 相机位于玩家头部
        cam_x = target.getX()
        cam_y = target.getY()
        cam_z = target.getZ() + self.FP_EYE_HEIGHT

        self._base.camera.setPos(cam_x, cam_y, cam_z)

        # 计算视线方向注视点
        heading_rad = math.radians(self._fp_heading)
        pitch_rad = math.radians(self._fp_pitch)
        look_dist = 10.0
        look_x = cam_x + look_dist * math.cos(pitch_rad) * math.sin(heading_rad)
        look_y = cam_y - look_dist * math.cos(pitch_rad) * math.cos(heading_rad)
        look_z = cam_z + look_dist * math.sin(pitch_rad)

        self._base.camera.lookAt(look_x, look_y, look_z)
