"""Bureautique (Word / Excel / PowerPoint / OpenDocument).

Deux moteurs possibles, tous deux 100 % locaux :
  - LibreOffice (gratuit) en mode headless, avec un profil dédié pour ne pas gêner
    une fenêtre LibreOffice déjà ouverte ;
  - Microsoft Office via COM, si installé (meilleur rendu PDF pour les .docx/.xlsx/.pptx).
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import threading
from functools import lru_cache
from pathlib import Path

from . import ConversionError, Task, run_hidden
from ..formats import category_of
from ..outputs import OutputCtx
from ..settings import Settings, cache_dir

IS_WIN = sys.platform == "win32"

# --- Détection ---------------------------------------------------------------------------

def find_soffice(settings: Settings) -> str | None:
    if settings.soffice_path and Path(settings.soffice_path).is_file():
        return settings.soffice_path
    cands: list[Path] = []
    if IS_WIN:
        try:
            import winreg
            for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                try:
                    with winreg.OpenKey(hive, r"SOFTWARE\LibreOffice\UNO\InstallPath") as k:
                        cands.append(Path(winreg.QueryValueEx(k, "")[0]) / "soffice.exe")
                except OSError:
                    pass
        except ImportError:
            pass
        for env in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
            if os.environ.get(env):
                cands.append(Path(os.environ[env]) / "LibreOffice" / "program" / "soffice.exe")
    for c in cands:
        if c.is_file():
            return str(c)
    return shutil.which("soffice") or shutil.which("libreoffice")


@lru_cache(maxsize=None)
def has_ms(app: str) -> bool:
    """app = 'Word' | 'Excel' | 'PowerPoint'"""
    if not IS_WIN:
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, rf"{app}.Application\CLSID"):
            pass
        import win32com.client  # noqa: F401
        return True
    except Exception:
        return False


MS_APP = {"word": "Word", "sheet": "Excel", "csv": "Excel", "slides": "PowerPoint"}

# Sorties possibles par catégorie et par moteur
LO_TARGETS = {"word": {"pdf", "docx", "odt", "rtf", "txt", "html"},
              "sheet": {"pdf", "xlsx", "ods", "csv"},
              "csv": {"pdf", "ods", "xlsx"},
              "slides": {"pdf", "pptx", "odp"}}
MS_TARGETS = {"word": {"pdf", "docx", "odt", "rtf", "txt", "html"},
              "sheet": {"pdf", "xlsx", "ods", "csv"},
              "csv": {"pdf", "ods", "xlsx"},
              "slides": {"pdf", "pptx", "odp"}}
MS_NATIVE = {"doc", "docx", "docm", "dot", "dotx", "rtf", "xls", "xlsx", "xlsm", "csv",
             "ppt", "pptx", "pptm", "pps", "ppsx"}


def engine_for(category: str, target: str, src_ext: str, settings: Settings) -> str | None:
    """'ms' | 'lo' | None"""
    lo_ok = target in LO_TARGETS.get(category, ()) and find_soffice(settings) is not None
    app = MS_APP.get(category)
    ms_ok = bool(app) and target in MS_TARGETS.get(category, ()) and has_ms(app)
    pref = settings.office_engine
    if pref == "libreoffice":
        return "lo" if lo_ok else ("ms" if ms_ok else None)
    if pref == "msoffice":
        return "ms" if ms_ok else ("lo" if lo_ok else None)
    # auto : Office pour ses propres formats, LibreOffice pour l'OpenDocument
    if ms_ok and (src_ext in MS_NATIVE or not lo_ok):
        return "ms"
    return "lo" if lo_ok else ("ms" if ms_ok else None)


def available(category: str, target: str, settings: Settings) -> bool:
    return any(engine_for(category, target, e, settings) for e in ("docx", "odt"))


# --- LibreOffice -------------------------------------------------------------------------

LO_FILTER = {
    "pdf": "pdf", "docx": "docx:MS Word 2007 XML", "odt": "odt", "rtf": "rtf",
    "txt": "txt:Text (encoded):UTF8", "html": "html",
    "xlsx": "xlsx:Calc MS Excel 2007 XML", "ods": "ods",
    "csv": "csv:Text - txt - csv (StarCalc):44,34,76,1",
    "pptx": "pptx:Impress MS PowerPoint 2007 XML", "odp": "odp",
}
_lo_lock = threading.Lock()  # une instance LibreOffice à la fois


def _lo_convert(soffice: str, src: Path, target: str, out: Path, settings: Settings) -> None:
    filt = LO_FILTER[target]
    if target == "csv" and settings.csv_delimiter == ";":
        filt = "csv:Text - txt - csv (StarCalc):59,34,76,1"
    profile = (cache_dir() / "lo-profile").as_uri()
    with tempfile.TemporaryDirectory(prefix="mue-lo-") as td, _lo_lock:
        args = [soffice, f"-env:UserInstallation={profile}", "--headless", "--norestore",
                "--nolockcheck", "--nodefault", "--convert-to", filt, "--outdir", td, str(src)]
        try:
            r = run_hidden(args, timeout=600)
        except Exception as e:
            raise ConversionError(f"LibreOffice n'a pas répondu ({type(e).__name__}).")
        produced = Path(td) / f"{src.stem}.{target}"
        if not produced.exists():
            cands = list(Path(td).glob(f"*.{target}"))
            if not cands:
                msg = (r.stderr or r.stdout).decode("utf-8", "replace").strip().splitlines()
                raise ConversionError("LibreOffice : " + (msg[-1] if msg else "conversion impossible."))
            produced = cands[0]
        shutil.move(str(produced), str(out))


# --- Microsoft Office (COM) ------------------------------------------------------------

WORD_FMT = {"docx": 16, "odt": 23, "rtf": 6, "txt": 2, "html": 10}
XL_FMT = {"xlsx": 51, "ods": 60, "csv": 62}
PPT_FMT = {"pdf": 32, "pptx": 24, "odp": 35}
_ms_lock = threading.Lock()


def _ms_convert(category: str, src: Path, target: str, out: Path, settings: Settings) -> None:
    import pythoncom
    import win32com.client as wc
    pythoncom.CoInitialize()
    try:
        with _ms_lock:
            if category == "word":
                app = wc.DispatchEx("Word.Application")
                app.Visible = False
                app.DisplayAlerts = 0
                try:
                    doc = app.Documents.Open(str(src), ConfirmConversions=False, ReadOnly=True,
                                             AddToRecentFiles=False, Visible=False)
                    try:
                        if target == "pdf":
                            doc.ExportAsFixedFormat(OutputFileName=str(out), ExportFormat=17)
                        elif target == "txt":
                            doc.SaveAs2(str(out), FileFormat=2, Encoding=65001)
                        else:
                            doc.SaveAs2(str(out), FileFormat=WORD_FMT[target])
                    finally:
                        doc.Close(False)
                finally:
                    if app.Documents.Count == 0:
                        app.Quit()
            elif category in ("sheet", "csv"):
                local = settings.csv_delimiter == ";"  # séparateur régional (FR = ;)
                app = wc.DispatchEx("Excel.Application")
                app.Visible = False
                app.DisplayAlerts = False
                try:
                    wb = app.Workbooks.Open(str(src), UpdateLinks=0, ReadOnly=True)
                    try:
                        if target == "pdf":
                            wb.ExportAsFixedFormat(0, str(out))
                        else:
                            try:
                                wb.SaveAs(str(out), FileFormat=XL_FMT[target], Local=local)
                            except Exception:
                                if target != "csv":
                                    raise
                                wb.SaveAs(str(out), FileFormat=6, Local=local)  # Excel ancien
                    finally:
                        wb.Close(SaveChanges=False)
                finally:
                    if app.Workbooks.Count == 0:
                        app.Quit()
            else:
                app = wc.DispatchEx("PowerPoint.Application")
                try:
                    pres = app.Presentations.Open(str(src), ReadOnly=True, Untitled=False, WithWindow=False)
                    try:
                        pres.SaveAs(str(out), PPT_FMT[target])
                    finally:
                        pres.Close()
                finally:
                    if app.Presentations.Count == 0:  # ne ferme pas un PowerPoint déjà ouvert
                        app.Quit()
    except ConversionError:
        raise
    except Exception as e:
        raise ConversionError(f"Microsoft Office : {getattr(e, 'excepinfo', None) and e.excepinfo[2] or e}")
    finally:
        pythoncom.CoUninitialize()


# --- Point d'entrée ----------------------------------------------------------------------

def convert(src: Path, target: str, ctx: OutputCtx, task: Task, settings: Settings) -> None:
    category = category_of(src.name)
    ext = src.suffix.lower().lstrip(".")
    eng = engine_for(category, target, ext, settings)
    if eng is None:
        raise ConversionError("Il faut LibreOffice (gratuit) ou Microsoft Office pour ce format.")
    task.progress(0.1)
    out = ctx.file(target)
    if eng == "ms":
        _ms_convert(category, src, target, out, settings)
    else:
        _lo_convert(find_soffice(settings), src, target, out, settings)
    if not out.exists() or out.stat().st_size == 0:
        raise ConversionError("La conversion n'a produit aucun fichier.")
    task.progress(1.0)
