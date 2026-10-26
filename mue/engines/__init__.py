"""Moteurs de conversion. Chaque moteur expose convert(src, target, ctx, task)."""

from __future__ import annotations

import subprocess
import sys
import threading
from dataclasses import dataclass, field
from typing import Callable


class ConversionError(Exception):
    """Erreur affichable telle quelle à l'utilisateur (en français)."""


class Cancelled(Exception):
    pass


@dataclass
class Task:
    """Ce qu'un moteur reçoit pour signaler sa progression et savoir s'il doit s'arrêter."""
    progress: Callable[[float], None] = lambda f: None
    cancel: threading.Event = field(default_factory=threading.Event)

    def check(self) -> None:
        if self.cancel.is_set():
            raise Cancelled()


# Pas de fenêtre console qui clignote quand on lance ffmpeg / soffice depuis l'appli fenêtrée
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def run_hidden(args: list[str], timeout: float | None = None, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, timeout=timeout, creationflags=NO_WINDOW,
                          stdin=subprocess.DEVNULL, **kw)


def popen_hidden(args: list[str], **kw) -> subprocess.Popen:
    return subprocess.Popen(args, creationflags=NO_WINDOW, stdin=subprocess.DEVNULL, **kw)
