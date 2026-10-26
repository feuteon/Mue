"""PDF et livres numériques via PyMuPDF : PDF -> images/texte, EPUB/XPS/CBZ -> PDF,
images -> PDF, fusion de PDF/images."""

from __future__ import annotations

from pathlib import Path

from . import ConversionError, Task
from ..formats import category_of
from ..outputs import OutputCtx
from ..settings import Settings


def _pm():
    import pymupdf
    return pymupdf


def _open(src: Path):
    pm = _pm()
    try:
        doc = pm.open(src)
    except Exception:
        raise ConversionError("Document illisible ou corrompu.")
    if doc.needs_pass:
        doc.close()
        raise ConversionError("Ce PDF est protégé par un mot de passe.")
    if doc.is_reflowable:  # EPUB, FB2… : mise en page A5
        doc.layout(rect=pm.paper_rect("a5"), fontsize=11)
    return doc


def pdf_to_images(src: Path, target: str, ctx: OutputCtx, task: Task, settings: Settings) -> None:
    pm = _pm()
    doc = _open(src)
    try:
        n = doc.page_count
        if n == 0:
            raise ConversionError("Le document ne contient aucune page.")
        zoom = max(36, min(600, settings.pdf_dpi)) / 72
        mat = pm.Matrix(zoom, zoom)
        if n == 1:
            outs = [ctx.file(target)]
        else:
            folder = ctx.folder_out(f"{src.stem} (pages)")
            width = max(3, len(str(n)))
            outs = [folder / f"{src.stem}-{i + 1:0{width}d}.{target}" for i in range(n)]
        for i, page in enumerate(doc):
            task.check()
            pix = page.get_pixmap(matrix=mat, alpha=False)
            if target == "jpg":
                pix.save(outs[i], output="jpeg", jpg_quality=settings.jpeg_quality)
            else:
                pix.save(outs[i])
            task.progress((i + 1) / n)
    finally:
        doc.close()


def to_text(src: Path, ctx: OutputCtx, task: Task, settings: Settings) -> None:
    doc = _open(src)
    try:
        parts = []
        n = doc.page_count or 1
        for i, page in enumerate(doc):
            task.check()
            parts.append(page.get_text("text"))
            task.progress((i + 1) / n * 0.95)
        text = "\n\f\n".join(p.rstrip() for p in parts)
        if not text.strip():
            raise ConversionError("Aucun texte trouvé (document scanné ? il faudrait de l'OCR).")
        ctx.file("txt").write_text(text, encoding="utf-8-sig")
    finally:
        doc.close()
    task.progress(1.0)


def to_pdf(src: Path, ctx: OutputCtx, task: Task, settings: Settings) -> None:
    """EPUB/XPS/CBZ/FB2/MOBI ou SVG -> PDF."""
    pm = _pm()
    doc = _open(src)
    try:
        task.progress(0.2)
        pdf = pm.open("pdf", doc.convert_to_pdf())
        task.check()
        pdf.save(ctx.file("pdf"), garbage=3, deflate=True)
        pdf.close()
    finally:
        doc.close()
    task.progress(1.0)


A4 = (595.28, 841.89)


def _add_image_page(pdf, src: Path, settings: Settings) -> None:
    pm = _pm()
    from .images import image_bytes_for_pdf
    data, w, h, dpi = image_bytes_for_pdf(src, settings)
    if settings.pdf_page == "a4":
        pw, ph = A4 if h >= w else (A4[1], A4[0])
        scale = min(pw / w, ph / h)
        iw, ih = w * scale, h * scale
        page = pdf.new_page(width=pw, height=ph)
        rect = pm.Rect((pw - iw) / 2, (ph - ih) / 2, (pw + iw) / 2, (ph + ih) / 2)
    else:
        pw, ph = w * 72 / dpi, h * 72 / dpi
        page = pdf.new_page(width=pw, height=ph)
        rect = page.rect
    page.insert_image(rect, stream=data)


def merge_to_pdf(srcs: list[Path], ctx: OutputCtx, task: Task, settings: Settings,
                 stem: str | None = None) -> None:
    """Images et/ou PDF -> un seul PDF, dans l'ordre donné."""
    pm = _pm()
    out = pm.open()
    n = len(srcs)
    try:
        for i, s in enumerate(srcs):
            task.check()
            cat = category_of(s.name)
            if cat in ("pdf", "ebook", "svg"):
                d = _open(s)
                if cat == "pdf":
                    out.insert_pdf(d)
                else:
                    tmp = pm.open("pdf", d.convert_to_pdf())
                    out.insert_pdf(tmp)
                    tmp.close()
                d.close()
            elif cat in ("image", "gif", "raw"):
                _add_image_page(out, s, settings)
            else:
                raise ConversionError(f"« {s.name} » ne peut pas être mis dans un PDF.")
            task.progress((i + 1) / n * 0.95)
        if out.page_count == 0:
            raise ConversionError("Rien à mettre dans le PDF.")
        out.save(ctx.file("pdf", stem=stem), garbage=3, deflate=True)
    finally:
        out.close()
    task.progress(1.0)
