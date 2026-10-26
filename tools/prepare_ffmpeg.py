"""Copie le ffmpeg.exe fourni par le paquet pip imageio-ffmpeg dans build/bin/ffmpeg.exe,
pour qu'il soit embarqué dans Mue (pas besoin d'installer FFmpeg à part)."""

import shutil
import sys
from pathlib import Path

import imageio_ffmpeg

root = Path(__file__).resolve().parents[1]
src = Path(imageio_ffmpeg.get_ffmpeg_exe())
dst = root / "build" / "bin" / ("ffmpeg.exe" if sys.platform == "win32" else "ffmpeg")
dst.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(src, dst)
print(f"ffmpeg : {src} -> {dst} ({dst.stat().st_size / 1e6:.0f} Mo)")
