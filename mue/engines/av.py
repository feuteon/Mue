"""Audio / vidéo via FFmpeg.

Stratégie : on « sonde » le fichier (codecs, durée), puis on tente d'abord la voie rapide
(copie des flux sans réencodage quand le conteneur cible les accepte — un MKV H.264 vers
MP4 prend 2 secondes au lieu de 2 minutes), et on retombe sur un réencodage complet si
ça échoue."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from . import Cancelled, ConversionError, NO_WINDOW, Task, run_hidden
from ..outputs import OutputCtx
from ..settings import Settings


# --- Localisation de ffmpeg ------------------------------------------------------------

def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parents[2]


def find_ffmpeg(settings: Settings) -> str | None:
    exe = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    candidates = []
    if settings.ffmpeg_path:
        candidates.append(Path(settings.ffmpeg_path))
    base = app_dir()
    candidates += [base / "bin" / exe, base / "_internal" / "bin" / exe, base / exe]
    for c in candidates:
        if c.is_file():
            return str(c)
    try:
        import imageio_ffmpeg
        p = imageio_ffmpeg.get_ffmpeg_exe()
        if p and Path(p).is_file():
            return p
    except Exception:
        pass
    return shutil.which("ffmpeg")


@lru_cache(maxsize=4)
def encoders(ffmpeg: str) -> frozenset[str]:
    try:
        out = run_hidden([ffmpeg, "-hide_banner", "-encoders"], timeout=20).stdout.decode("utf-8", "replace")
    except Exception:
        return frozenset()
    names = set()
    for line in out.splitlines():
        m = re.match(r"\s*[VAS][\w.]{5}\s+(\S+)", line)
        if m:
            names.add(m.group(1))
    return frozenset(names)


@lru_cache(maxsize=4)
def version(ffmpeg: str) -> str:
    try:
        out = run_hidden([ffmpeg, "-hide_banner", "-version"], timeout=20).stdout.decode("utf-8", "replace")
        m = re.search(r"ffmpeg version (\S+)", out)
        return m.group(1) if m else "?"
    except Exception:
        return "?"


# --- Sondage ---------------------------------------------------------------------------

@dataclass
class Stream:
    kind: str           # video | audio | subtitle | data | attachment
    codec: str
    attached_pic: bool = False
    hi_bits: bool = False   # audio 24/32 bits


@dataclass
class Info:
    duration: float = 0.0
    streams: list[Stream] = field(default_factory=list)

    @property
    def video(self) -> list[Stream]:
        return [s for s in self.streams if s.kind == "video" and not s.attached_pic]

    @property
    def audio(self) -> list[Stream]:
        return [s for s in self.streams if s.kind == "audio"]

    @property
    def cover(self) -> Stream | None:
        return next((s for s in self.streams if s.attached_pic), None)


_STREAM_RE = re.compile(r"Stream #\d+:\d+\S*: (Video|Audio|Subtitle|Data|Attachment): ([^\s,]+)(.*)")
_DUR_RE = re.compile(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)")


def probe(ffmpeg: str, src: Path) -> Info:
    try:
        r = run_hidden([ffmpeg, "-hide_banner", "-nostdin", "-i", str(src)], timeout=60)
    except subprocess.TimeoutExpired:
        raise ConversionError("FFmpeg ne répond pas en lisant ce fichier.")
    text = r.stderr.decode("utf-8", "replace")
    info = Info()
    m = _DUR_RE.search(text)
    if m:
        h, mi, s = m.groups()
        info.duration = int(h) * 3600 + int(mi) * 60 + float(s)
    for m in _STREAM_RE.finditer(text):
        kind, codec, rest = m.group(1).lower(), m.group(2).lower(), m.group(3)
        info.streams.append(Stream(kind, codec, "attached pic" in rest,
                                   "24 bit" in rest or "s32" in rest))
    if not info.streams:
        if "Invalid data" in text or "could not find codec" in text.lower():
            raise ConversionError("Fichier audio/vidéo illisible ou corrompu.")
        raise ConversionError("Aucun flux audio ou vidéo trouvé dans ce fichier.")
    return info


# --- Recettes ---------------------------------------------------------------------------

VIDEO_PRESETS = {
    # x264 preset/crf, vp9 cpu-used/crf
    "fast": ("veryfast", 23, 5, 34),
    "balanced": ("faster", 21, 4, 31),
    "best": ("slow", 18, 2, 28),
}

EVEN = "scale=trunc(iw/2)*2:trunc(ih/2)*2"

# Conteneur -> (vidéos copiables, audios copiables)
COPYABLE = {
    "mp4": ({"h264", "hevc", "av1"}, {"aac", "mp3", "ac3", "eac3", "alac", "opus", "flac"}),
    "mov": ({"h264", "hevc", "prores", "mjpeg"}, {"aac", "mp3", "alac", "ac3", "pcm_s16le", "pcm_s24le"}),
    "webm": ({"vp8", "vp9", "av1"}, {"opus", "vorbis"}),
    "avi": ({"mpeg4", "msmpeg4v2", "msmpeg4v3", "mjpeg"}, {"mp3", "ac3", "pcm_s16le"}),
}


def _vorbis_q(br: int) -> str:
    return str(4 if br <= 128 else 6 if br <= 192 else 8 if br <= 256 else 9)


def audio_codec_args(target: str, s: Settings, enc: frozenset[str], hi_bits: bool) -> list[str]:
    br = max(64, min(320, s.audio_bitrate))
    if target == "mp3":
        return ["-c:a", "libmp3lame", "-b:a", f"{br}k"]
    if target in ("m4a", "aac"):
        return ["-c:a", "aac", "-b:a", f"{br}k"]
    if target == "opus":
        return ["-c:a", "libopus", "-b:a", f"{min(br, 256)}k"]
    if target == "ogg":
        if "libvorbis" in enc:
            return ["-c:a", "libvorbis", "-q:a", _vorbis_q(br)]
        return ["-c:a", "libopus", "-b:a", f"{min(br, 256)}k"]
    if target == "flac":
        return ["-c:a", "flac", "-compression_level", "5"]
    if target == "wav":
        return ["-c:a", "pcm_s24le" if hi_bits else "pcm_s16le"]
    if target == "aiff":
        return ["-c:a", "pcm_s24be" if hi_bits else "pcm_s16be"]
    raise ConversionError(f"Sortie audio inconnue : {target}")


def video_encode_args(target: str, s: Settings) -> list[str]:
    x_preset, x_crf, vp_cpu, vp_crf = VIDEO_PRESETS.get(s.video_quality, VIDEO_PRESETS["balanced"])
    if target == "webm":
        return ["-c:v", "libvpx-vp9", "-crf", str(vp_crf), "-b:v", "0", "-deadline", "good",
                "-cpu-used", str(vp_cpu), "-row-mt", "1", "-pix_fmt", "yuv420p", "-vf", EVEN]
    if target == "avi":
        return ["-c:v", "mpeg4", "-vtag", "xvid", "-q:v", "3", "-vf", EVEN]
    return ["-c:v", "libx264", "-preset", x_preset, "-crf", str(x_crf), "-pix_fmt", "yuv420p", "-vf", EVEN]


def video_audio_args(target: str, s: Settings) -> list[str]:
    br = max(96, min(320, s.audio_bitrate))
    if target == "webm":
        return ["-c:a", "libopus", "-b:a", f"{min(br, 256)}k"]
    if target == "avi":
        return ["-c:a", "libmp3lame", "-b:a", f"{br}k"]
    return ["-c:a", "aac", "-b:a", f"{br}k"]


def attempts_for(info: Info, target: str, s: Settings, enc: frozenset[str], src_ext: str) -> list[tuple[str, list[str]]]:
    """Liste ordonnée de (description, options de sortie) à essayer."""
    hi = any(a.hi_bits for a in info.audio)
    fast_mov = ["-movflags", "+faststart"] if target in ("mp4", "mov") else []

    # --- Sortie audio (depuis un audio ou une vidéo) ---
    if target in ("mp3", "wav", "flac", "ogg", "opus", "m4a", "aiff"):
        if not info.audio:
            raise ConversionError("Ce fichier ne contient aucune piste audio.")
        a = audio_codec_args(target, s, enc, hi)
        tries = []
        if info.cover and target in ("mp3", "flac", "m4a") and not info.video:
            extra = ["-id3v2_version", "3"] if target == "mp3" else []
            tries.append(("avec pochette", ["-map", "0:a:0", "-map", "0:v:0", "-c:v", "copy",
                                             "-disposition:v:0", "attached_pic", *a, *extra]))
        tries.append(("audio", ["-map", "0:a:0", "-vn", "-sn", *a]))
        tries.append(("stéréo", ["-map", "0:a:0", "-vn", "-sn", *a, "-ac", "2"]))  # 5.1 exotique -> stéréo
        return tries

    # --- GIF animé ---
    if target == "gif":
        if not info.video:
            raise ConversionError("Aucune piste vidéo à transformer en GIF.")
        w, fps = max(32, s.gif_width), max(1, min(50, s.gif_fps))
        vf = (f"fps={fps},scale='min({w},iw)':-1:flags=lanczos,split[a][b];"
              f"[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle")
        return [("gif", ["-map", "0:V:0", "-an", "-sn", "-vf", vf, "-loop", "0"])]

    # --- Vidéo ---
    if not info.video:
        raise ConversionError("Ce fichier ne contient aucune piste vidéo.")
    venc, aenc = video_encode_args(target, s), video_audio_args(target, s)
    tries: list[tuple[str, list[str]]] = []
    vcodecs = {v.codec for v in info.video}
    acodecs = {a.codec for a in info.audio}

    if target == "mkv":
        tries.append(("remux", ["-map", "0", "-map", "-0:d", "-c", "copy"]))
        tries.append(("réencodage", ["-map", "0:V", "-map", "0:a?", "-map", "0:s?", *venc, *aenc, "-c:s", "copy"]))
        tries.append(("réencodage", ["-map", "0:V:0", "-map", "0:a?", "-sn", *venc, *aenc]))
        return tries

    vok, aok = COPYABLE[target]
    copy_v = vcodecs <= vok and src_ext != "gif"
    copy_a = acodecs <= aok
    if copy_v or (copy_a and info.audio):
        v = ["-c:v", "copy"] if copy_v else venc
        if copy_v and target in ("mp4", "mov") and vcodecs == {"hevc"}:
            v += ["-tag:v", "hvc1"]  # lisible par QuickTime / Apple
        a = ["-c:a", "copy"] if copy_a else aenc
        label = "remux" if (copy_v and (copy_a or not info.audio)) else "partiel"
        tries.append((label, ["-map", "0:V", "-map", "0:a?", "-sn", "-dn", *v, *a, *fast_mov]))
    tries.append(("réencodage", ["-map", "0:V:0", "-map", "0:a?", "-sn", "-dn", *venc, *aenc, *fast_mov]))
    tries.append(("réencodage stéréo", ["-map", "0:V:0", "-map", "0:a:0?", "-sn", "-dn", *venc, *aenc,
                                        "-ac", "2", *fast_mov]))
    return tries


# --- Exécution --------------------------------------------------------------------------

_TIME_RE = re.compile(r"out_time=(\d+):(\d+):(\d+(?:\.\d+)?)")


def run_ffmpeg(ffmpeg: str, src: Path, opts: list[str], out: Path, duration: float,
               task: Task, p0: float, p1: float) -> tuple[bool, str]:
    args = [ffmpeg, "-hide_banner", "-nostdin", "-y", "-loglevel", "error", "-i", str(src),
            *opts, "-progress", "pipe:1", "-nostats", str(out)]
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            stdin=subprocess.DEVNULL, creationflags=NO_WINDOW)
    err_chunks: list[bytes] = []

    def drain():
        for chunk in iter(lambda: proc.stderr.read(4096), b""):
            err_chunks.append(chunk)
            if len(err_chunks) > 64:
                del err_chunks[:32]

    t = threading.Thread(target=drain, daemon=True)
    t.start()
    def watch_cancel():
        while proc.poll() is None:
            if task.cancel.wait(0.25):
                proc.kill()
                return

    threading.Thread(target=watch_cancel, daemon=True).start()
    for raw in iter(proc.stdout.readline, b""):
        line = raw.decode("ascii", "ignore").strip()
        m = _TIME_RE.match(line)
        if m and duration > 0:
            h, mi, sec = m.groups()
            cur = int(h) * 3600 + int(mi) * 60 + float(sec)
            task.progress(p0 + (p1 - p0) * max(0.0, min(1.0, cur / duration)))
    proc.wait()
    t.join(timeout=2)
    if task.cancel.is_set():
        raise Cancelled()
    err = b"".join(err_chunks).decode("utf-8", "replace").strip()
    return proc.returncode == 0, err


def _friendly(err: str) -> str:
    last = [l for l in err.splitlines() if l.strip()]
    msg = last[-1] if last else "erreur inconnue"
    return f"FFmpeg : {msg[:220]}"


def convert(src: Path, target: str, ctx: OutputCtx, task: Task, settings: Settings) -> None:
    ffmpeg = find_ffmpeg(settings)
    if not ffmpeg:
        raise ConversionError("FFmpeg introuvable. Indique son chemin dans les réglages de Mue.")
    task.progress(0.01)
    info = probe(ffmpeg, src)
    enc = encoders(ffmpeg)
    tries = attempts_for(info, target, settings, enc, src.suffix.lower().lstrip("."))
    out = ctx.file(target)
    last_err = ""
    for i, (_label, opts) in enumerate(tries):
        task.check()
        ok, err = run_ffmpeg(ffmpeg, src, opts, out, info.duration, task, 0.02, 0.99)
        if ok and out.exists() and out.stat().st_size > 0:
            task.progress(1.0)
            return
        last_err = err
        try:
            if out.exists():
                out.unlink()
        except OSError:
            pass
        task.progress(0.02)
    raise ConversionError(_friendly(last_err))
