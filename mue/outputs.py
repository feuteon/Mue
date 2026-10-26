"""Gestion des fichiers de sortie : choix d'un nom libre, écriture dans un fichier
temporaire puis renommage atomique (pas de fichier à moitié écrit en cas d'échec)."""

from __future__ import annotations

import os
import shutil
import threading
import uuid
from pathlib import Path

from .settings import Settings

_lock = threading.Lock()
_reserved: set[str] = set()


def _key(p: Path) -> str:
    return os.path.normcase(str(p))


def _free_name(folder: Path, stem: str, ext: str | None) -> Path:
    """Premier nom libre : « photo.png », sinon « photo (1).png », « photo (2).png »…"""
    def make(i: int) -> Path:
        name = stem if i == 0 else f"{stem} ({i})"
        return folder / (f"{name}.{ext}" if ext else name)

    with _lock:
        i = 0
        while True:
            cand = make(i)
            if not cand.exists() and _key(cand) not in _reserved:
                _reserved.add(_key(cand))
                return cand
            i += 1


def _release(p: Path) -> None:
    with _lock:
        _reserved.discard(_key(p))


class OutputCtx:
    """Un moteur demande ses sorties via file()/folder(), écrit dans le chemin temporaire
    retourné, puis le gestionnaire appelle commit() (succès) ou rollback() (échec)."""

    def __init__(self, src: Path, settings: Settings):
        self.src = src
        if settings.output_mode == "subfolder":
            self.folder = src.parent / (settings.subfolder_name.strip() or "Converti")
        else:
            self.folder = src.parent
        self._items: list[tuple[Path, Path]] = []   # (temporaire, final)

    def _ensure_folder(self) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)

    def file(self, ext: str, stem: str | None = None) -> Path:
        self._ensure_folder()
        final = _free_name(self.folder, stem or self.src.stem, ext)
        tmp = self.folder / f".{final.stem}.mue-{uuid.uuid4().hex[:8]}.{ext}"
        self._items.append((tmp, final))
        return tmp

    def folder_out(self, stem: str | None = None) -> Path:
        self._ensure_folder()
        final = _free_name(self.folder, stem or self.src.stem, None)
        tmp = self.folder / f".{final.name}.mue-{uuid.uuid4().hex[:8]}"
        tmp.mkdir()
        self._items.append((tmp, final))
        return tmp

    def commit(self) -> list[Path]:
        done = []
        for tmp, final in self._items:
            if not tmp.exists():
                _release(final)
                continue
            os.replace(tmp, final)
            _release(final)
            done.append(final)
        self._items.clear()
        return done

    def rollback(self) -> None:
        for tmp, final in self._items:
            try:
                if tmp.is_dir():
                    shutil.rmtree(tmp, ignore_errors=True)
                elif tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
            _release(final)
        self._items.clear()
