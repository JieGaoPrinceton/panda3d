# -*- mode: python ; coding: utf-8 -*-
# MyPanda3DGame.spec  —  PyInstaller macOS 打包配置
# 用法: cd my_game && pyinstaller MyPanda3DGame.spec

import os
import sys
import glob

# ── Panda3D 安装路径 ──
P3D_ROOT = '/Library/Developer/Panda3D'
P3D_LIB  = os.path.join(P3D_ROOT, 'lib')
P3D_ETC  = os.path.join(P3D_ROOT, 'etc')
P3D_PKG  = os.path.join(P3D_ROOT, 'panda3d')
DIRECT   = os.path.join(P3D_ROOT, 'direct')

# ── 收集所有 Panda3D dylib ──
panda_dylibs = []
for dylib in glob.glob(os.path.join(P3D_LIB, '*.dylib')):
    # 只保留无版本号的符号链接（避免重复）
    basename = os.path.basename(dylib)
    if '1.11' not in basename:
        panda_dylibs.append((dylib, '.'))

# ── 收集 panda3d Python 扩展模块 (.so) ──
panda_so = []
for so in glob.glob(os.path.join(P3D_PKG, '*.so')):
    panda_so.append((so, 'panda3d'))

# ── 游戏资源文件 ──
game_datas = [
    # Panda3D 配置
    ('config.prc',              '.'),
    # 3D 模型
    ('assets/models',           'assets/models'),
    # 音效
    ('assets/sounds',           'assets/sounds'),
    # 存档
    ('saves',                   'saves'),
    # 源码包（作为数据，运行时 import）
    ('src',                     'src'),
    # Panda3D etc 配置
    (os.path.join(P3D_ETC, 'Config.prc'),      'etc'),
    (os.path.join(P3D_ETC, 'Confauto.prc'),    'etc'),
]

# ── 合并所有 binaries ──
all_binaries = panda_dylibs + panda_so

# ── 合并所有 datas ──
all_datas = game_datas

a = Analysis(
    ['main.py'],
    pathex=[
        '.',
        P3D_ROOT,
        os.path.join(P3D_ROOT, 'direct'),
    ],
    binaries=all_binaries,
    datas=all_datas,
    hiddenimports=[
        # Panda3D 核心
        'panda3d.core',
        'panda3d.bullet',
        'panda3d.direct',
        'panda3d.egg',
        'panda3d.physics',
        'panda3d.fx',
        # direct 子包
        'direct.showbase.ShowBase',
        'direct.showbase.DirectObject',
        'direct.task.Task',
        'direct.task.TaskManagerGlobal',
        'direct.fsm.FSM',
        'direct.fsm.ClassicFSM',
        'direct.gui.DirectGui',
        'direct.gui.DirectButton',
        'direct.gui.DirectLabel',
        'direct.gui.DirectFrame',
        'direct.gui.DirectSlider',
        'direct.gui.DirectScrolledList',
        'direct.gui.OnscreenText',
        'direct.gui.OnscreenImage',
        'direct.interval.IntervalGlobal',
        'direct.interval.LerpInterval',
        'direct.interval.FunctionInterval',
        'direct.interval.MetaInterval',
        'direct.particles.ParticleEffect',
        'direct.particles.Particles',
        'direct.particles.ForceGroup',
        'direct.filter.CommonFilters',
        'direct.stdpy.file',
        # 游戏子模块
        'src.physics',
        'src.player',
        'src.camera',
        'src.audio',
        'src.picking',
        'src.scene',
        'src.collectibles',
        'src.shadows',
        'src.fog',
        'src.skybox',
        'src.post_processing',
        'src.day_night',
        'src.collision',
        'src.npc',
        'src.save_load',
        'src.minimap',
        'src.dialogue',
        'src.exit_dialog',
        'src.hud',
        'src.settings_panel',
        'src.game_fsm',
        'src.animations',
        'src.particles_fx',
        'src.constants',
        # 标准库
        'json',
        'os',
        'sys',
        'math',
        'random',
        'typing',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'scipy',
        'PIL',
        'cv2',
        'wx',
        'PyQt5',
        'PyQt6',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MyPanda3DGame',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,   # GUI 应用，不显示终端
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch='arm64',
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='MyPanda3DGame',
)

app = BUNDLE(
    coll,
    name='MyPanda3DGame.app',
    icon=None,          # 可替换为 .icns 文件路径
    bundle_identifier='com.mygame.panda3d',
    version='0.7.0',
    info_plist={
        'CFBundleName':              'MyPanda3DGame',
        'CFBundleDisplayName':       'My Panda3D Game',
        'CFBundleVersion':           '0.7.0',
        'CFBundleShortVersionString':'0.7.0',
        'CFBundleIdentifier':        'com.mygame.panda3d',
        'NSHighResolutionCapable':   True,
        'NSPrincipalClass':          'NSApplication',
        'LSMinimumSystemVersion':    '11.0',
        'NSHumanReadableCopyright':  'Copyright © 2026 Panda3D Game Dev',
        # 允许访问文件系统（存档）
        'com.apple.security.app-sandbox': False,
    },
)
