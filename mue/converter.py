"""Aiguillage : pour un fichier et une cible, quel moteur ? Et quelles cibles proposer
dans le menu pour une extension donnée ?"""

from __future__ import annotations

from pathlib import Path

from .engines import ConversionError, Task
from .formats import CATEGORIES, MENUS, SEP, category_of, norm_ext
from .outputs import OutputCtx
from .settings import Settings

AV_TARGETS = {"mp4", "mkv", "webm", "mov", "avi", "mp3", "wav", "flac", "ogg", "opus", "m4a", "aiff"}


def _engine_name(category: str, target: str, src_ext: str) -> str | None:
    if target == "pdfmerge":
        return "merge" if category in ("image", "gif", "pdf", "raw", "svg") else None
    if category in ("image", "raw"):
        return "docs-merge1" if target == "pdf" else "images"
    if category == "gif":
        if target in ("mp4", "webm"):
            return "av"
        return "docs-merge1" if target == "pdf" else "images"
    if category == "svg":
        return "docs-pdf" if target == "pdf" else "images"
    if category in ("audio", "video"):
        return "av"
    if category == "pdf":
        return "docs-text" if target == "txt" else "docs-images"
    if category == "ebook":
        return "docs-text" if target == "txt" else "docs-pdf"
    if category in ("sheet", "csv", "json"):
        from .engines import data
        if data.supports(src_ext, target):
            return "data"
        return None if category == "json" else "office"
    if category in ("word", "slides"):
        return "office"
    return None


def is_available(category: str, target: str, settings: Settings, src_ext: str | None = None) -> bool:
    """La cible est-elle réalisable sur cette machine ? (utilisé pour construire le menu)"""
    ext = src_ext or next(iter(sorted(CATEGORIES[category])))
    eng = _engine_name(category, target, ext)
    if eng is None:
        return False
    if eng == "images":
        from .engines import images
        if category == "raw" and not images.HAS_RAW:
            return False
        return images.supports(target)
    if eng == "av":
        from .engines import av
        ff = av.find_ffmpeg(settings)
        if not ff:
            return False
        enc = av.encoders(ff)
        need = {"mp4": "libx264", "mov": "libx264", "mkv": "libx264", "webm": "libvpx-vp9",
                "avi": "mpeg4", "mp3": "libmp3lame", "opus": "libopus", "m4a": "aac", "flac": "flac"}
        return not enc or target not in need or need[target] in enc
    if eng == "office":
        from .engines import office
        return any(office.engine_for(category, target, e, settings) for e in CATEGORIES[category])
    return True


def menu_for_ext(ext: str, settings: Settings) -> list:
    """Entrées du sous-menu pour une extension : liste de (cible, libellé) et de SEP."""
    ext = ext.lower().lstrip(".")
    cat = category_of(ext)
    if not cat:
        return []
    if cat == "image":
        from .engines import images
        if ext in ("heic", "heif") and not images.HAS_HEIF:
            return []
    if cat == "raw":
        from .engines import images
        if not images.HAS_RAW:
            return []
    self_ext = norm_ext(ext)
    items: list = []
    for it in MENUS[cat]:
        if it is SEP:
            if items and items[-1] is not SEP:
                items.append(SEP)
            continue
        target, label = it
        if target == self_ext:
            continue
        if not _ext_ok(cat, target, ext, settings):
            continue
        items.append(it)
    while items and items[-1] is SEP:
        items.pop()
    return items


def _ext_ok(cat: str, target: str, ext: str, settings: Settings) -> bool:
    if cat in ("sheet", "csv"):
        eng = _engine_name(cat, target, ext)
        if eng == "data":
            return True
        if eng == "office":
            from .engines import office
            return office.engine_for(cat, target, ext, settings) is not None
        return False
    return is_available(cat, target, settings, ext)


def convert_one(src: Path, target: str, task: Task, settings: Settings) -> list[Path]:
    """Convertit un fichier. Retourne les chemins produits (fichiers ou dossier)."""
    if not src.exists():
        raise ConversionError("Le fichier n'existe plus.")
    cat = category_of(src.name)
    if not cat:
        raise ConversionError(f"Extension « {src.suffix} » non prise en charge.")
    ext = src.suffix.lower().lstrip(".")
    eng = _engine_name(cat, target, ext)
    if eng is None:
        raise ConversionError(f"Conversion {ext.upper()} → {target.upper()} non prise en charge.")
    ctx = OutputCtx(src, settings)
    try:
        if eng == "images":
            from .engines import images
            images.convert(src, target, ctx, task, settings)
        elif eng == "av":
            from .engines import av
            av.convert(src, target, ctx, task, settings)
        elif eng == "docs-images":
            from .engines import docs
            docs.pdf_to_images(src, target, ctx, task, settings)
        elif eng == "docs-text":
            from .engines import docs
            docs.to_text(src, ctx, task, settings)
        elif eng == "docs-pdf":
            from .engines import docs
            docs.to_pdf(src, ctx, task, settings)
        elif eng == "docs-merge1":
            from .engines import docs
            docs.merge_to_pdf([src], ctx, task, settings)
        elif eng == "data":
            from .engines import data
            data.convert(src, target, ctx, task, settings)
        elif eng == "office":
            from .engines import office
            office.convert(src, target, ctx, task, settings)
        else:
            raise ConversionError("Moteur inconnu.")
        return ctx.commit()
    except BaseException:
        ctx.rollback()
        raise


def merge(srcs: list[Path], task: Task, settings: Settings) -> list[Path]:
    from .engines import docs
    srcs = [s for s in srcs if s.exists()]
    if not srcs:
        raise ConversionError("Aucun fichier à fusionner.")
    ctx = OutputCtx(srcs[0], settings)
    stem = f"{srcs[0].stem} - fusion"
    try:
        docs.merge_to_pdf(srcs, ctx, task, settings, stem=stem)
        return ctx.commit()
    except BaseException:
        ctx.rollback()
        raise
