"""Réglages persistants (JSON dans %APPDATA%\\Mue)."""

from __future__ import annotations

import json
import os
import sys
import threading
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from . import APP_NAME


def data_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    d = base / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    d = base / APP_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


@dataclass
class Settings:
    # Sortie
    output_mode: str = "same"            # "same" (à côté) | "subfolder"
    subfolder_name: str = "Converti"
    # Images
    jpeg_quality: int = 92
    webp_quality: int = 88
    avif_quality: int = 70
    keep_metadata: bool = True
    background: str = "#FFFFFF"          # fond quand on retire la transparence (JPG, BMP…)
    svg_min_size: int = 1024             # taille mini (px, plus grand côté) d'un rendu SVG
    pdf_dpi: int = 200                   # PDF -> images
    pdf_page: str = "a4"                 # images -> PDF : "a4" | "image"
    # Vidéo / audio
    video_quality: str = "balanced"      # "fast" | "balanced" | "best"
    audio_bitrate: int = 256             # kb/s pour MP3 / AAC / Opus
    gif_fps: int = 15
    gif_width: int = 480
    # Données
    csv_delimiter: str = ","
    # Bureautique
    office_engine: str = "auto"          # "auto" | "libreoffice" | "msoffice"
    # Comportement
    auto_close: bool = True
    open_folder_when_done: bool = False
    # Chemins personnalisés (vide = auto)
    ffmpeg_path: str = ""
    soffice_path: str = ""

    @classmethod
    def load(cls) -> "Settings":
        s = cls()
        try:
            raw = json.loads((data_dir() / "settings.json").read_text("utf-8"))
            names = {f.name: f.type for f in fields(cls)}
            for k, v in raw.items():
                if k in names and isinstance(v, type(getattr(s, k))):
                    setattr(s, k, v)
        except (OSError, ValueError):
            pass
        return s

    def save(self) -> None:
        path = data_dir() / "settings.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), "utf-8")
        os.replace(tmp, path)


_lock = threading.Lock()
_current: Settings | None = None


def get() -> Settings:
    global _current
    with _lock:
        if _current is None:
            _current = Settings.load()
        return _current


def reload() -> Settings:
    global _current
    with _lock:
        _current = Settings.load()
        return _current
