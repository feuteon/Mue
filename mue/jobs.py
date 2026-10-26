"""File d'attente des conversions (côté Qt) : reçoit les demandes, les répartit sur des
threads de travail, publie l'avancement via des signaux."""

from __future__ import annotations

import itertools
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from . import converter
from .engines import Cancelled, ConversionError, Task
from .formats import category_of
from .settings import Settings

_ids = itertools.count(1)

QUEUED, RUNNING, DONE, FAILED, CANCELLED = "queued", "running", "done", "failed", "cancelled"


@dataclass
class Job:
    srcs: list[Path]
    target: str
    id: int = field(default_factory=lambda: next(_ids))
    status: str = QUEUED
    progress: float = 0.0
    outputs: list[Path] = field(default_factory=list)
    error: str = ""
    started: float = 0.0
    ended: float = 0.0
    task: Task = field(default_factory=Task)

    @property
    def src(self) -> Path:
        return self.srcs[0]

    @property
    def is_merge(self) -> bool:
        return self.target == "pdfmerge"

    @property
    def category(self) -> str:
        return category_of(self.src.name) or ""

    @property
    def heavy(self) -> bool:
        return self.category in ("video", "audio", "word", "sheet", "slides", "csv") or \
            (self.category == "gif" and self.target in ("mp4", "webm"))

    @property
    def finished(self) -> bool:
        return self.status in (DONE, FAILED, CANCELLED)


class JobManager(QObject):
    added = pyqtSignal(object)          # Job
    changed = pyqtSignal(object)        # Job
    idle = pyqtSignal()                 # plus rien en cours ni en attente
    incoming = pyqtSignal(dict)         # message IPC (émis depuis un autre thread)

    MERGE_DELAY_MS = 900

    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings
        self.jobs: list[Job] = []
        cpu = os.cpu_count() or 4
        self._pool = ThreadPoolExecutor(max_workers=max(2, min(6, cpu // 2)), thread_name_prefix="mue")
        self._heavy = threading.Semaphore(2 if cpu >= 8 else 1)   # ffmpeg/office : 2 max en parallèle
        self._merge_buf: list[Path] = []
        self._merge_timer = QTimer(self, singleShot=True, interval=self.MERGE_DELAY_MS)
        self._merge_timer.timeout.connect(self._flush_merge)
        self.incoming.connect(self.submit_message)

    # --- Entrées ---------------------------------------------------------------------

    def submit_message(self, msg: dict) -> None:
        target = str(msg.get("target", ""))
        paths = [Path(p) for p in msg.get("paths", []) if isinstance(p, str)]
        if target and paths:
            self.submit(target, paths)

    def submit(self, target: str, paths: list[Path]) -> None:
        if target == "pdfmerge":
            for p in paths:
                if p not in self._merge_buf:
                    self._merge_buf.append(p)
            self._merge_timer.start()  # (re)lance l'attente : on regroupe toute la sélection
            return
        for p in paths:
            if any(j.src == p and j.target == target and not j.finished for j in self.jobs):
                continue  # doublon (double-clic dans le menu…)
            self._start(Job([p], target))

    def _flush_merge(self) -> None:
        if not self._merge_buf:
            return
        srcs = sorted(self._merge_buf, key=lambda p: _natural_key(p.name))
        self._merge_buf = []
        self._start(Job(srcs, "pdfmerge"))

    def _start(self, job: Job) -> None:
        self.jobs.append(job)
        self.added.emit(job)
        self._pool.submit(self._run, job)

    # --- Exécution (threads de travail) ---------------------------------------------

    def _run(self, job: Job) -> None:
        if job.task.cancel.is_set():
            self._finish(job, CANCELLED)
            return
        sem = self._heavy if job.heavy else None
        if sem:
            sem.acquire()
        try:
            if job.task.cancel.is_set():
                self._finish(job, CANCELLED)
                return
            job.status, job.started = RUNNING, time.monotonic()
            self.changed.emit(job)
            last = [0.0, 0.0]

            def progress(f: float) -> None:
                now = time.monotonic()
                if f >= 1.0 or f - last[0] >= 0.01 and now - last[1] >= 0.08:
                    last[0], last[1] = f, now
                    job.progress = max(job.progress, min(1.0, f))
                    self.changed.emit(job)

            job.task.progress = progress
            if job.is_merge:
                job.outputs = converter.merge(job.srcs, job.task, self.settings)
            else:
                job.outputs = converter.convert_one(job.src, job.target, job.task, self.settings)
            job.progress = 1.0
            self._finish(job, DONE)
        except Cancelled:
            self._finish(job, CANCELLED)
        except ConversionError as e:
            job.error = str(e)
            self._finish(job, FAILED)
        except MemoryError:
            job.error = "Mémoire insuffisante pour ce fichier."
            self._finish(job, FAILED)
        except PermissionError:
            job.error = "Accès refusé : impossible d'écrire dans ce dossier."
            self._finish(job, FAILED)
        except Exception as e:  # erreur inattendue : on l'affiche plutôt que de planter
            job.error = f"Erreur inattendue : {type(e).__name__}: {e}"[:300]
            self._finish(job, FAILED)
        finally:
            if sem:
                sem.release()

    def _finish(self, job: Job, status: str) -> None:
        job.status, job.ended = status, time.monotonic()
        self.changed.emit(job)

    # --- Commandes -------------------------------------------------------------------

    def cancel_all(self) -> None:
        self._merge_buf.clear()
        self._merge_timer.stop()
        for j in self.jobs:
            if not j.finished:
                j.task.cancel.set()

    def cancel(self, job: Job) -> None:
        job.task.cancel.set()

    def busy(self) -> bool:
        return bool(self._merge_buf) or self._merge_timer.isActive() or \
            any(not j.finished for j in self.jobs)

    def counts(self) -> tuple[int, int, int]:
        done = sum(1 for j in self.jobs if j.status == DONE)
        failed = sum(1 for j in self.jobs if j.status in (FAILED, CANCELLED))
        return done, failed, len(self.jobs)

    def shutdown(self) -> None:
        self.cancel_all()
        self._pool.shutdown(wait=False, cancel_futures=True)


def _natural_key(s: str):
    import re
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]
