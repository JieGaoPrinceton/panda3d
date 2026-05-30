"""
src/minimap.py — 小地图系统
==============================
演示 Panda3D 的多相机 / DisplayRegion：
- 独立俯视相机
- 右下角小地图 DisplayRegion
- 玩家 / NPC / 经验方块标记

引擎对应: base.makeCamera() · DisplayRegion · render-to-texture
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Optional

from panda3d.core import (
    NodePath, PandaNode, Camera, OrthographicLens,
    Vec3, Vec4, CardMaker, Texture,
    WindowProperties, FrameBufferProperties,
    GraphicsPipe, GraphicsOutput,
    GeomVertexFormat, GeomVertexData, GeomVertexWriter,
    Geom, GeomTriangles, GeomNode,
    LVector4f,
)

if TYPE_CHECKING:
    from direct.showbase.ShowBase import ShowBase
    from .player import PlayerController


class MiniMap:
    """右下角俯视小地图。"""

    def __init__(self, base: ShowBase, size: float = 0.3) -> None:
        self._base = base
        self._enabled = False
        self._size = size  # 小地图占屏幕比例

        # 小地图相机高度
        self._cam_height = 80.0
        self._view_range = 50.0  # 正交视野范围

        # 创建小地图 DisplayRegion
        self._setup_minimap()

    def _setup_minimap(self) -> None:
        """创建小地图的 DisplayRegion 和相机。"""
        # 在主窗口右下角创建一个 DisplayRegion
        dr = self._base.win.makeDisplayRegion(
            1.0 - self._size, 1.0,  # 右侧
            0.0, self._size,         # 底部
        )
        dr.setSort(20)  # 在主场景之后渲染
        dr.setClearColorActive(True)
        dr.setClearColor(Vec4(0.1, 0.15, 0.1, 1))
        dr.setClearDepthActive(True)

        self._display_region = dr

        # 创建正交相机（俯视）
        cam_node = Camera("minimap_cam")
        lens = OrthographicLens()
        lens.setFilmSize(self._view_range, self._view_range)
        lens.setNearFar(1, 200)
        cam_node.setLens(lens)

        self._cam_np = self._base.render.attachNewNode(cam_node)
        self._cam_np.setPos(0, 20, self._cam_height)
        self._cam_np.lookAt(0, 20, 0)

        dr.setCamera(self._cam_np)

        # 创建玩家标记（小红色圆圈）
        self._player_marker = self._create_circle_marker(
            "player_marker", Vec4(1, 0.2, 0.2, 1), radius=1.5, segments=16
        )

        # 默认隐藏
        self._display_region.setActive(False)

    def _create_circle_marker(self, name: str, color: Vec4,
                              radius: float = 1.5,
                              segments: int = 16) -> NodePath:
        """创建一个圆形标记（程序化几何体）。

        使用三角扇形（中心点 + 外圈顶点）生成圆形，
        替代 CardMaker 的方块标记。
        """
        # 顶点格式：位置 + 颜色
        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData(name, fmt, Geom.UHStatic)
        vdata.setNumRows(segments + 1)

        vertex = GeomVertexWriter(vdata, "vertex")
        color_w = GeomVertexWriter(vdata, "color")

        # 中心点（顶点 0）
        vertex.addData3(0, 0, 0)
        color_w.addData4(color)

        # 外圈顶点（顶点 1 ~ segments）
        for i in range(segments):
            angle = 2.0 * math.pi * i / segments
            x = radius * math.cos(angle)
            y = radius * math.sin(angle)
            vertex.addData3(x, y, 0)
            color_w.addData4(color)

        # 三角形索引（扇形）
        tris = GeomTriangles(Geom.UHStatic)
        for i in range(segments):
            tris.addVertices(0, i + 1, (i + 1) % segments + 1)
        tris.closePrimitive()

        geom = Geom(vdata)
        geom.addPrimitive(tris)

        geom_node = GeomNode(f"{name}_geom")
        geom_node.addGeom(geom)

        marker = self._base.render.attachNewNode(geom_node)
        marker.setLightOff()
        marker.setShaderOff()
        marker.setBillboardPointEye()  # 始终面向相机
        marker.setBin("fixed", 100)
        marker.setDepthTest(False)
        marker.setDepthWrite(False)
        return marker

    def enable(self) -> None:
        """显示小地图。"""
        self._display_region.setActive(True)
        self._player_marker.show()
        self._enabled = True

    def disable(self) -> None:
        """隐藏小地图。"""
        self._display_region.setActive(False)
        self._player_marker.hide()
        self._enabled = False

    def toggle(self) -> bool:
        """切换小地图显示。"""
        if self._enabled:
            self.disable()
        else:
            self.enable()
        return self._enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    def update(self, player_pos) -> None:
        """每帧更新小地图。"""
        if not self._enabled:
            return

        # 小地图相机跟随玩家
        px = player_pos.getX()
        py = player_pos.getY()
        self._cam_np.setPos(px, py, self._cam_height)
        self._cam_np.lookAt(px, py, 0)

        # 更新玩家标记位置
        self._player_marker.setPos(px, py, 0.5)

    def set_view_range(self, range_val: float) -> None:
        """设置小地图视野范围。"""
        self._view_range = max(20, min(200, range_val))
        lens = self._cam_np.node().getLens()
        lens.setFilmSize(self._view_range, self._view_range)

    def cleanup(self) -> None:
        """清理小地图资源。"""
        if self._display_region:
            self._base.win.removeDisplayRegion(self._display_region)
        if self._cam_np:
            self._cam_np.removeNode()
        if self._player_marker:
            self._player_marker.removeNode()
