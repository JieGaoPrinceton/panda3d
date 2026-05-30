# ──────────────────────────────────────────────
# Panda3D 运行时配置文件  config.prc
# 文档: https://docs.panda3d.org/1.11/python/programming/configuration/index
# ──────────────────────────────────────────────

# 窗口标题（会被 WindowProperties 覆盖）
window-title My Panda3D Game

# 分辨率 & 显示模式
win-size 1280 720
fullscreen 0

# 帧率上限（0 = 不限制）
clock-mode limited
clock-frame-rate 60

# 显示帧率
show-frame-rate-meter 0

# 多重采样抗锯齿（0=关闭, 2/4/8=开启）
framebuffer-multisample 1
multisamples 4

# 音频驱动（openal-soft 在 Mac 上兼容性最好）
audio-library-name p3openal_audio

# 日志等级: spam / debug / info / warning / error / fatal
notify-level warning
default-directnotify-level warning

# 模型搜索路径（相对于 main.py 所在目录）
model-path .
model-path assets/models

# 纹理各向异性过滤
texture-anisotropic-degree 4

# 开启颜色校正（sRGB）
framebuffer-srgb 1
