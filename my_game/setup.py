#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
my_game/setup.py  —  Panda3D bdist_apps 打包配置
=================================================
用法:
    cd /Users/mac/code/panda3d-master/my_game
    python3 setup.py bdist_apps

输出:
    build/bdist.macosx-*/  →  MyPanda3DGame.app
    dist/                  →  MyPanda3DGame-macOS.dmg (zip)
"""

from setuptools import setup

APP_NAME = "MyPanda3DGame"
APP_VERSION = "0.7.0"
APP_AUTHOR = "Panda3D Game Dev"

setup(
    name=APP_NAME,
    version=APP_VERSION,
    author=APP_AUTHOR,
    options={
        "build_apps": {
            # ── 入口脚本 ──
            "gui_apps": {
                APP_NAME: "main.py",
            },

            # ── 需要打包进去的数据文件（相对于 setup.py 所在目录）──
            "include_patterns": [
                # 配置文件
                "config.prc",
                # 3D 模型
                "assets/models/**",
                # 音效
                "assets/sounds/**",
                # 存档目录（空目录占位）
                "saves/.gitkeep",
                # 源码包
                "src/**/*.py",
            ],

            # ── 排除不需要的文件 ──
            "exclude_patterns": [
                "**/__pycache__/**",
                "**/*.pyc",
                "**/*.pyo",
                "build/**",
                "dist/**",
                "*.pdf",
                "*.svg",
                "*.md",
                "setup.py",
            ],

            # ── 目标平台 ──
            "platforms": ["macosx_11_0_arm64"],

            # ── 插件（Panda3D 渲染/音频/物理插件）──
            "plugins": [
                "pandagl",          # OpenGL 渲染器
                "p3openal_audio",   # OpenAL 音频
                "p3bullet",         # Bullet 物理引擎（如果作为插件）
            ],

            # ── 额外的 Python 包 ──
            "include_modules": {
                "*": [
                    "direct.showbase.ShowBase",
                    "direct.task",
                    "direct.fsm",
                    "direct.gui",
                    "direct.interval",
                    "direct.particles",
                    "panda3d.core",
                    "panda3d.bullet",
                    "panda3d.direct",
                ],
            },

            # ── 日志级别 ──
            "log_filename": "$USER_APPDATA/MyPanda3DGame/output.log",
            "log_append": False,
        },

        "bdist_apps": {
            # macOS 默认打包为 zip（包含 .app）
            "installers": {
                "macosx_11_0_arm64": ["zip"],
            },
        },
    },
)
