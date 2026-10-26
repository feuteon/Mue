"""Catalogue des formats : quelles extensions on reconnaît, et quel menu « Convertir vers »
on propose pour chacune. Le menu réellement installé est filtré selon les moteurs
disponibles (voir converter.available_targets)."""

from __future__ import annotations

SEP = None  # séparateur dans le menu

# --- Extensions reconnues, par catégorie ------------------------------------------------

CATEGORIES: dict[str, set[str]] = {
    "image": {"jpg", "jpeg", "jfif", "jpe", "png", "webp", "bmp", "dib", "tif", "tiff",
              "ico", "heic", "heif", "avif", "tga", "psd", "jp2", "pcx", "ppm", "qoi"},
    "gif": {"gif"},
    "svg": {"svg"},
    "raw": {"cr2", "cr3", "nef", "nrw", "arw", "srf", "sr2", "dng", "orf", "rw2", "raf",
            "pef", "srw", "3fr", "erf", "kdc", "mrw", "x3f", "iiq"},
    "audio": {"mp3", "wav", "flac", "ogg", "oga", "opus", "m4a", "aac", "wma", "aiff", "aif",
              "aifc", "amr", "ape", "mka", "wv", "ac3", "dts", "caf", "mpc", "tta", "m4b"},
    "video": {"mp4", "mkv", "mov", "avi", "webm", "wmv", "flv", "m4v", "mpg", "mpeg", "ts",
              "mts", "m2ts", "3gp", "3g2", "ogv", "vob", "f4v", "asf", "divx", "mxf"},
    "pdf": {"pdf"},
    "ebook": {"epub", "xps", "oxps", "cbz", "fb2", "mobi"},
    "word": {"doc", "docx", "docm", "dot", "dotx", "odt", "rtf", "wpd"},
    "sheet": {"xls", "xlsx", "xlsm", "ods"},
    "csv": {"csv"},
    "json": {"json"},
    "slides": {"ppt", "pptx", "pptm", "pps", "ppsx", "odp"},
}

# Extension -> extension « canonique » (pour ne pas proposer JPG sur un .jpeg, etc.)
SAME_AS = {"jpeg": "jpg", "jfif": "jpg", "jpe": "jpg", "tif": "tiff", "aif": "aiff",
           "aifc": "aiff", "oga": "ogg", "dib": "bmp", "m4b": "m4a", "pps": "ppt",
           "ppsx": "pptx", "pptm": "pptx", "docm": "docx", "xlsm": "xlsx"}

# --- Menus par catégorie : (clé cible, libellé) ---------------------------------------
# La clé cible est l'extension produite (sauf "pdfmerge").

MENUS: dict[str, list] = {
    "image": [("png", "PNG"), ("jpg", "JPG"), ("webp", "WEBP"), ("avif", "AVIF"),
              ("gif", "GIF"), ("bmp", "BMP"), ("tiff", "TIFF"), ("ico", "ICO — icône"), SEP,
              ("pdf", "PDF"), ("pdfmerge", "PDF — fusionner la sélection")],
    "gif": [("webp", "WEBP (animé)"), ("png", "PNG"), ("jpg", "JPG"), ("bmp", "BMP"),
            ("tiff", "TIFF"), ("ico", "ICO — icône"), SEP,
            ("mp4", "MP4 (vidéo)"), ("webm", "WEBM (vidéo)"), SEP,
            ("pdf", "PDF")],
    "svg": [("png", "PNG"), ("jpg", "JPG"), ("webp", "WEBP"), ("ico", "ICO — icône"), SEP,
            ("pdf", "PDF (vectoriel)")],
    "raw": [("jpg", "JPG"), ("png", "PNG"), ("tiff", "TIFF"), ("webp", "WEBP"), ("avif", "AVIF")],
    "audio": [("mp3", "MP3"), ("wav", "WAV"), ("flac", "FLAC"), ("ogg", "OGG"),
              ("opus", "OPUS"), ("m4a", "M4A (AAC)"), ("aiff", "AIFF")],
    "video": [("mp4", "MP4"), ("mkv", "MKV"), ("webm", "WEBM"), ("mov", "MOV"), ("avi", "AVI"), SEP,
              ("gif", "GIF animé"), SEP,
              ("mp3", "MP3 — audio seul"), ("wav", "WAV — audio seul")],
    "pdf": [("png", "PNG — une image par page"), ("jpg", "JPG — une image par page"),
            ("txt", "TXT — texte brut"), SEP,
            ("pdfmerge", "PDF — fusionner la sélection")],
    "ebook": [("pdf", "PDF"), ("txt", "TXT — texte brut")],
    "word": [("pdf", "PDF"), ("docx", "DOCX (Word)"), ("odt", "ODT"), ("rtf", "RTF"),
             ("txt", "TXT"), ("html", "HTML")],
    "sheet": [("pdf", "PDF"), ("xlsx", "XLSX (Excel)"), ("ods", "ODS"), ("csv", "CSV"),
              ("json", "JSON")],
    "csv": [("xlsx", "XLSX (Excel)"), ("json", "JSON"), SEP, ("pdf", "PDF"), ("ods", "ODS")],
    "json": [("csv", "CSV"), ("xlsx", "XLSX (Excel)")],
    "slides": [("pdf", "PDF"), ("pptx", "PPTX (PowerPoint)"), ("odp", "ODP")],
}

CATEGORY_LABELS = {
    "image": "Images", "gif": "GIF", "svg": "SVG", "raw": "Photos RAW", "audio": "Audio",
    "video": "Vidéo", "pdf": "PDF", "ebook": "Livres numériques", "word": "Textes (Word…)",
    "sheet": "Tableurs", "csv": "CSV", "json": "JSON", "slides": "Présentations",
}

EXT_TO_CATEGORY: dict[str, str] = {e: c for c, exts in CATEGORIES.items() for e in exts}


def norm_ext(ext: str) -> str:
    ext = ext.lower().lstrip(".")
    return SAME_AS.get(ext, ext)


def category_of(path_or_ext: str) -> str | None:
    s = str(path_or_ext)
    ext = s.rsplit(".", 1)[-1].lower() if "." in s else s.lower()
    return EXT_TO_CATEGORY.get(ext)


def label_for(category: str, target: str) -> str:
    for item in MENUS.get(category, []):
        if item and item[0] == target:
            return item[1]
    return target.upper()
