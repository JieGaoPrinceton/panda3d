"""
src/audio.py — 音效系统
"""

from __future__ import annotations

from typing import Dict, Optional, TYPE_CHECKING

from panda3d.core import AudioSound

from .constants import SFX_BASE, DEFAULTS

if TYPE_CHECKING:
    from direct.showbase.ShowBase import ShowBase


class AudioManager:
    """音效加载与播放管理。"""

    def __init__(self, base: ShowBase) -> None:
        self._base = base
        self._sfx: Dict[str, Optional[AudioSound]] = {}
        self.volume = DEFAULTS["sfx_volume"]

        sfx_map = {
            "jump": f"{SFX_BASE}/GUI_click.wav",
            "pick": f"{SFX_BASE}/GUI_rollover.wav",
            "spawn": f"{SFX_BASE}/GUI_click.wav",
            "delete": f"{SFX_BASE}/GUI_rollover.wav",
        }

        for name, path in sfx_map.items():
            try:
                snd = base.loader.loadSfx(path)
                if snd:
                    snd.setVolume(self.volume)
                self._sfx[name] = snd
            except Exception:
                self._sfx[name] = None

    def play(self, name: str) -> None:
        """播放指定音效。"""
        snd = self._sfx.get(name)
        if snd and snd.status() != AudioSound.PLAYING:
            snd.setVolume(self.volume)
            snd.play()

    def set_volume(self, vol: float) -> None:
        """设置全局音效音量。"""
        self.volume = max(0.0, min(1.0, vol))
        for snd in self._sfx.values():
            if snd:
                snd.setVolume(self.volume)
