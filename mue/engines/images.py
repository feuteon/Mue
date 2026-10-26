"""Images : Pillow (+ pillow-heif pour HEIC, rawpy pour les RAW, PyMuPDF pour le SVG)."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageOps, features

from . import ConversionError, Task
from ..outputs import OutputCtx
from ..settings import Settings

Image.MAX_IMAGE_PIXELS = 400_000_000  # grosses images OK, mais garde-fou anti-bombe

try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HAS_HEIF = True
except Exception:  # pragma: no cover
    HAS_HEIF = False

try:
    import rawpy  # noqa: F401
    HAS_RAW = True
except Exception:  # pragma: no cover
    HAS_RAW = False

HAS_AVIF = bool(features.check("avif")) if hasattr(features, "check") else False

PIL_FORMAT = {"png": "PNG", "jpg": "JPEG", "webp": "WEBP", "avif": "AVIF", "gif": "GIF",
              "bmp": "BMP", "tiff": "TIFF", "ico": "ICO"}
ANIMATABLE = {"gif", "webp"}
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]


def supports(target: str) -> bool:
    if target == "avif":
        return HAS_AVIF
    return target in PIL_FORMAT


# --- Ouverture ---------------------------------------------------------------------------

def open_any(src: Path, settings: Settings) -> Image.Image:
    ext = src.suffix.lower().lstrip(".")
    if ext == "svg":
        return render_svg(src, settings.svg_min_size)
    from ..formats import CATEGORIES
    if ext in CATEGORIES["raw"]:
        if not HAS_RAW:
            raise ConversionError("Le support des photos RAW n'est pas installé (rawpy).")
        import rawpy
        with rawpy.imread(str(src)) as raw:
            rgb = raw.postprocess(use_camera_wb=True, output_bps=8)
        return Image.fromarray(rgb)
    try:
        img = Image.open(src)
    except Image.UnidentifiedImageError:
        raise ConversionError("Image illisible ou format non reconnu.")
    return img


def render_svg(src: Path, min_size: int) -> Image.Image:
    import pymupdf
    try:
        doc = pymupdf.open(src)
    except Exception:
        raise ConversionError("SVG illisible.")
    page = doc[0]
    w, h = page.rect.width or 1, page.rect.height or 1
    scale = max(1.0, min_size / max(w, h))
    scale = min(scale, 16000 / max(w, h))
    pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=True)
    img = Image.frombytes("RGBA", (pix.width, pix.height), pix.samples)
    doc.close()
    return img


# --- Normalisation des modes ------------------------------------------------------------

def _has_alpha(img: Image.Image) -> bool:
    return img.mode in ("RGBA", "LA", "PA", "RGBa", "La") or \
        (img.mode == "P" and "transparency" in img.info)


def _to_8bit(img: Image.Image) -> Image.Image:
    if img.mode in ("I;16", "I;16B", "I;16L", "I;16N", "I"):
        return img.convert("I").point(lambda v: v * (1 / 256)).convert("L")
    if img.mode == "F":
        return img.convert("L")
    return img


def to_rgb(img: Image.Image, bg: str) -> Image.Image:
    img = _to_8bit(img)
    if _has_alpha(img):
        rgba = img.convert("RGBA")
        base = Image.new("RGB", rgba.size, bg)
        base.paste(rgba, mask=rgba.getchannel("A"))
        return base
    if img.mode in ("L", "1"):
        return img.convert("L")
    return img.convert("RGB") if img.mode != "RGB" else img


def to_rgba_or_rgb(img: Image.Image) -> Image.Image:
    img = _to_8bit(img)
    if _has_alpha(img):
        return img.convert("RGBA")
    if img.mode in ("RGB", "L"):
        return img
    return img.convert("RGB")


# --- Sauvegarde --------------------------------------------------------------------------

def _meta(img: Image.Image, settings: Settings) -> dict:
    if not settings.keep_metadata:
        return {}
    out = {}
    icc = img.info.get("icc_profile")
    if icc:
        out["icc_profile"] = icc
    try:
        exif = img.getexif()
        if exif:
            out["exif"] = exif.tobytes()
    except Exception:
        pass
    return out


def save_still(img: Image.Image, out: Path, target: str, settings: Settings) -> None:
    meta = _meta(img, settings)
    fmt = PIL_FORMAT[target]
    if target == "jpg":
        im = to_rgb(img, settings.background)
        q = max(1, min(100, settings.jpeg_quality))
        im.save(out, fmt, quality=q, optimize=True, progressive=True,
                subsampling=0 if q >= 90 else 2, **meta)
    elif target == "png":
        im = img if img.mode in ("1", "L", "LA", "P", "RGB", "RGBA", "I;16") else to_rgba_or_rgb(img)
        if im.mode == "P" and "transparency" in im.info:
            im = im.convert("RGBA")
        im.save(out, fmt, compress_level=7, **meta)
    elif target == "webp":
        im = to_rgba_or_rgb(img)
        im.save(out, fmt, quality=settings.webp_quality, method=5, **meta)
    elif target == "avif":
        im = to_rgba_or_rgb(img)
        im.save(out, fmt, quality=settings.avif_quality, **meta)
    elif target == "gif":
        im = to_rgba_or_rgb(img)
        if im.mode == "RGBA":
            # palette adaptative + index transparent
            alpha = im.getchannel("A")
            p = im.convert("RGB").convert("P", palette=Image.Palette.ADAPTIVE, colors=255)
            mask = alpha.point(lambda a: 255 if a < 128 else 0)
            p.paste(255, mask=mask)
            p.save(out, fmt, transparency=255, optimize=True)
        else:
            im.convert("P", palette=Image.Palette.ADAPTIVE, colors=256).save(out, fmt, optimize=True)
    elif target == "bmp":
        to_rgb(img, settings.background).save(out, fmt)
    elif target == "tiff":
        im = img if img.mode in ("RGB", "RGBA", "L", "LA", "CMYK", "1", "I;16") else to_rgba_or_rgb(img)
        im.save(out, fmt, compression="tiff_lzw", **meta)
    elif target == "ico":
        im = to_rgba_or_rgb(img).convert("RGBA")
        side = max(im.size)
        if im.width != im.height:  # carré centré sur fond transparent
            sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
            sq.paste(im, ((side - im.width) // 2, (side - im.height) // 2))
            im = sq
        if side > 256:
            im = im.resize((256, 256), Image.Resampling.LANCZOS)
        sizes = [(s, s) for s in ICO_SIZES if s <= max(im.size)] or [im.size]
        im.save(out, fmt, sizes=sizes)
    else:  # pragma: no cover
        raise ConversionError(f"Format de sortie inconnu : {target}")


def save_animated(img: Image.Image, out: Path, target: str, settings: Settings) -> None:
    frames, durations = [], []
    for i in range(img.n_frames):
        img.seek(i)
        frames.append(img.convert("RGBA"))
        durations.append(img.info.get("duration", 100) or 100)
    loop = img.info.get("loop", 0)
    first, rest = frames[0], frames[1:]
    if target == "webp":
        first.save(out, "WEBP", save_all=True, append_images=rest, duration=durations, loop=loop,
                   quality=settings.webp_quality, method=4)
    else:  # gif
        first.save(out, "GIF", save_all=True, append_images=rest, duration=durations, loop=loop,
                   disposal=2, optimize=False)


# --- Point d'entrée ----------------------------------------------------------------------

def load_oriented(src: Path, settings: Settings) -> Image.Image:
    img = open_any(src, settings)
    try:
        img = ImageOps.exif_transpose(img) or img
    except Exception:
        pass
    return img


def convert(src: Path, target: str, ctx: OutputCtx, task: Task, settings: Settings) -> None:
    if not supports(target):
        raise ConversionError(f"Sortie {target.upper()} non prise en charge sur cette machine.")
    task.progress(0.05)
    img = open_any(src, settings)
    task.check()
    animated = getattr(img, "n_frames", 1) > 1 and getattr(img, "is_animated", False)
    out = ctx.file(target)
    if animated and target in ANIMATABLE:
        save_animated(img, out, target, settings)
    else:
        if animated:
            img.seek(0)
        try:
            img = ImageOps.exif_transpose(img) or img
        except Exception:
            pass
        img.load()
        task.progress(0.5)
        save_still(img, out, target, settings)
    task.progress(1.0)


def image_bytes_for_pdf(src: Path, settings: Settings) -> tuple[bytes, int, int, float]:
    """Image prête à être posée sur une page PDF : (octets, largeur, hauteur, dpi).
    Un JPEG déjà droit est réutilisé tel quel (aucune recompression)."""
    img = open_any(src, settings)
    dpi = 150.0
    try:
        d = img.info.get("dpi", (0, 0))[0]
        if 50 <= float(d) <= 1200:
            dpi = float(d)
    except Exception:
        pass
    orientation = 1
    try:
        orientation = img.getexif().get(0x0112, 1)
    except Exception:
        pass
    if img.format == "JPEG" and orientation == 1 and img.mode in ("RGB", "L"):
        return src.read_bytes(), img.width, img.height, dpi
    img = ImageOps.exif_transpose(img) or img
    if getattr(img, "n_frames", 1) > 1:
        img.seek(0)
    buf = io.BytesIO()
    if _has_alpha(img):
        to_rgba_or_rgb(img).save(buf, "PNG")
    else:
        to_rgb(img, settings.background).save(buf, "JPEG", quality=92)
    return buf.getvalue(), img.width, img.height, dpi
