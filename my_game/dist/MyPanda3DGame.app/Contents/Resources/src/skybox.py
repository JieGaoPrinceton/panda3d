"""
src/skybox.py — 天空盒 / 程序化天空
====================================
演示 Panda3D 的天空渲染：
- 程序化渐变天空球
- 颜色可调（与日夜循环联动）

引擎对应: Shader + TextureStage · 球形天空盒
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from panda3d.core import (
    GeomVertexFormat, GeomVertexData, GeomVertexWriter,
    Geom, GeomTriangles, GeomNode,
    NodePath, Vec4, LVector3,
    Texture, TextureStage,
    ColorBlendAttrib, TransparencyAttrib,
    CompassEffect, BillboardEffect,
)
import math

if TYPE_CHECKING:
    from direct.showbase.ShowBase import ShowBase


class SkyBox:
    """程序化天空球。"""

    def __init__(self, base: ShowBase) -> None:
        self._base = base
        self._enabled = False

        # 天空颜色参数
        self._top_color = Vec4(0.2, 0.4, 0.8, 1.0)     # 天顶蓝色
        self._horizon_color = Vec4(0.7, 0.8, 0.95, 1.0)  # 地平线浅蓝
        self._bottom_color = Vec4(0.4, 0.45, 0.5, 1.0)   # 底部灰色

        # 创建天空球
        self._sky_np = self._create_sky_sphere(32, 16, 500.0)
        self._sky_np.setLightOff()       # 天空不受光照影响
        self._sky_np.setShaderOff()      # 天空不受 shader 影响
        self._sky_np.setBin("background", 0)  # 最先渲染
        self._sky_np.setDepthWrite(False)      # 不写深度
        self._sky_np.setDepthTest(False)       # 不测试深度

        # 天空球跟随相机（只跟随位置，不跟随旋转）
        self._sky_np.setEffect(CompassEffect.make(self._base.render))
        self._sky_np.reparentTo(self._base.camera)

        # 默认隐藏
        self._sky_np.hide()

    def _create_sky_sphere(self, segments: int, rings: int,
                           radius: float) -> NodePath:
        """程序化生成带顶点色的天空球。"""
        fmt = GeomVertexFormat.getV3c4()
        vdata = GeomVertexData("sky_sphere", fmt, Geom.UHStatic)

        vertex = GeomVertexWriter(vdata, "vertex")
        color = GeomVertexWriter(vdata, "color")

        # 生成顶点
        for i in range(rings + 1):
            phi = math.pi * i / rings  # 0 (顶) → π (底)
            t = i / rings  # 0 → 1

            # 颜色插值：顶 → 地平线 → 底
            if t < 0.5:
                # 顶 → 地平线
                f = t * 2.0
                c = self._top_color * (1 - f) + self._horizon_color * f
            else:
                # 地平线 → 底
                f = (t - 0.5) * 2.0
                c = self._horizon_color * (1 - f) + self._bottom_color * f

            for j in range(segments + 1):
                theta = 2.0 * math.pi * j / segments
                x = radius * math.sin(phi) * math.cos(theta)
                y = radius * math.sin(phi) * math.sin(theta)
                z = radius * math.cos(phi)

                vertex.addData3(x, y, z)
                color.addData4(c)

        # 生成三角形索引
        tris = GeomTriangles(Geom.UHStatic)
        for i in range(rings):
            for j in range(segments):
                v0 = i * (segments + 1) + j
                v1 = v0 + 1
                v2 = (i + 1) * (segments + 1) + j
                v3 = v2 + 1

                tris.addVertices(v0, v2, v1)
                tris.addVertices(v1, v2, v3)

        geom = Geom(vdata)
        geom.addPrimitive(tris)

        node = GeomNode("sky_sphere")
        node.addGeom(geom)

        return NodePath(node)

    def enable(self) -> None:
        """显示天空球。"""
        self._sky_np.show()
        self._enabled = True

    def disable(self) -> None:
        """隐藏天空球。"""
        self._sky_np.hide()
        self._enabled = False

    def toggle(self) -> bool:
        """切换天空球开关。"""
        if self._enabled:
            self.disable()
        else:
            self.enable()
        return self._enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_colors(self, top: Vec4, horizon: Vec4, bottom: Vec4) -> None:
        """设置天空颜色（用于日夜循环联动）。"""
        self._top_color = top
        self._horizon_color = horizon
        self._bottom_color = bottom
        # 重建天空球以更新颜色
        old_parent = self._sky_np.getParent()
        self._sky_np.removeNode()
        self._sky_np = self._create_sky_sphere(32, 16, 500.0)
        self._sky_np.setLightOff()
        self._sky_np.setShaderOff()
        self._sky_np.setBin("background", 0)
        self._sky_np.setDepthWrite(False)
        self._sky_np.setDepthTest(False)
        self._sky_np.setEffect(CompassEffect.make(self._base.render))
        self._sky_np.reparentTo(old_parent)
        if self._enabled:
            self._sky_np.show()
        else:
            self._sky_np.hide()

    @property
    def top_color(self) -> Vec4:
        return self._top_color

    @property
    def horizon_color(self) -> Vec4:
        return self._horizon_color

    @property
    def bottom_color(self) -> Vec4:
        return self._bottom_color
