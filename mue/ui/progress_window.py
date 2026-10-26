"""Fenêtre de progression : petite carte en bas à droite de l'écran, une ligne par fichier."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PyQt5.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QSize, Qt, QTimer
from PyQt5.QtGui import QColor, QCursor, QFont, QPainter
from PyQt5.QtWidgets import (QApplication, QFrame, QGraphicsDropShadowEffect, QHBoxLayout,
                             QLabel, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout,
                             QWidget)

from .. import APP_NAME
from ..formats import label_for
from ..jobs import CANCELLED, DONE, FAILED, QUEUED, RUNNING, Job, JobManager
from . import theme
from .widgets import Badge, ThinProgress, app_pixmap

ROW_H = 54
MAX_ROWS = 6
WIDTH = 420


def human_size(n: int) -> str:
    for unit in ("o", "Ko", "Mo", "Go"):
        if n < 1024 or unit == "Go":
            return f"{n:.0f} {unit}" if unit == "o" else f"{n:.1f} {unit}".replace(".", ",")
        n /= 1024
    return f"{n} o"


def out_size(paths: list[Path]) -> int:
    total = 0
    for p in paths:
        try:
            if p.is_dir():
                total += sum(f.stat().st_size for f in p.iterdir() if f.is_file())
            else:
                total += p.stat().st_size
        except OSError:
            pass
    return total


def reveal(path: Path) -> None:
    """Ouvre l'Explorateur avec le fichier sélectionné."""
    try:
        if sys.platform == "win32":
            subprocess.Popen(f'explorer /select,"{path}"')
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path.parent)])
    except OSError:
        pass


def elide(widget: QLabel, text: str, width: int) -> str:
    return widget.fontMetrics().elidedText(text, Qt.ElideMiddle, width)


class JobRow(QFrame):
    def __init__(self, job: Job, manager: JobManager, parent=None):
        super().__init__(parent)
        self.job, self.manager = job, manager
        self.setObjectName("JobRow")
        self.setFixedHeight(ROW_H)
        self.setAttribute(Qt.WA_Hover)
        self._hover = False

        src_ext = job.src.suffix.lstrip(".").upper() or "?"
        tgt = "PDF" if job.is_merge else job.target.upper()
        badge_txt = f"{len(job.srcs)} → PDF" if job.is_merge and len(job.srcs) > 1 else f"{src_ext} → {tgt}"
        color = theme.CATEGORY_COLORS.get(job.category, theme.VIOLET)
        self.badge = Badge(badge_txt, color)

        self.name = QLabel()
        self.name.setFont(theme.font(9.5, QFont.Medium))
        self.status = QLabel()
        self.status.setFont(theme.font(8.5))
        self.status.setProperty("muted", True)
        self.bar = ThinProgress(3)
        self.right = QLabel()
        self.right.setFont(theme.font(9, QFont.DemiBold))
        self.right.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.right.setFixedWidth(46)
        self.cancel_btn = QPushButton("✕")
        self.cancel_btn.setProperty("flat", True)
        self.cancel_btn.setFixedSize(26, 26)
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.setToolTip("Annuler ce fichier")
        self.cancel_btn.clicked.connect(lambda: manager.cancel(job))
        self.cancel_btn.hide()

        text_col = QVBoxLayout()
        text_col.setSpacing(4)
        text_col.setContentsMargins(0, 0, 0, 0)
        top = QHBoxLayout()
        top.setSpacing(8)
        top.addWidget(self.badge)
        top.addWidget(self.name, 1)
        text_col.addLayout(top)
        text_col.addWidget(self.status)
        text_col.addWidget(self.bar)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 6, 8, 6)
        lay.setSpacing(8)
        lay.addLayout(text_col, 1)
        lay.addWidget(self.right)
        lay.addWidget(self.cancel_btn)
        self.refresh()

    def _title(self) -> str:
        if self.job.is_merge and len(self.job.srcs) > 1:
            return f"{self.job.src.name} + {len(self.job.srcs) - 1} autre(s)"
        return self.job.src.name

    def refresh(self) -> None:
        j = self.job
        self.name.setText(elide(self.name, self._title(), 230))
        self.name.setToolTip(str(j.src))
        self.bar.setVisible(j.status in (QUEUED, RUNNING))
        self.status.setStyleSheet("")
        if j.status == QUEUED:
            self.status.setText("En attente…")
            self.right.setText("")
        elif j.status == RUNNING:
            self.status.setText("Conversion…" if j.progress < 0.995 else "Finalisation…")
            self.right.setText(f"{int(j.progress * 100)} %")
            self.right.setStyleSheet(f"color: {theme.MUTED};")
            self.bar.animate_to(j.progress)
        elif j.status == DONE:
            outs = j.outputs
            what = outs[0].name + ("/" if outs and outs[0].is_dir() else "") if outs else ""
            if len(outs) > 1:
                what = f"{len(outs)} fichiers"
            dur = max(0.0, j.ended - j.started)
            parts = [what, human_size(out_size(outs))]
            if dur >= 1:
                parts.append(f"{dur:.0f} s" if dur >= 10 else f"{dur:.1f} s".replace(".", ","))
            self.status.setText(elide(self.status, " · ".join(parts), 300))
            self.right.setText("✓")
            self.right.setStyleSheet(f"color: {theme.OK}; font-size: 13pt;")
            self.setToolTip("Cliquer pour afficher dans l'Explorateur")
            self.setCursor(Qt.PointingHandCursor)
        elif j.status == FAILED:
            self.status.setText(elide(self.status, j.error, 300))
            self.status.setStyleSheet(f"color: {theme.ERR};")
            self.right.setText("✕")
            self.right.setStyleSheet(f"color: {theme.ERR}; font-size: 12pt;")
            self.setToolTip(j.error)
        elif j.status == CANCELLED:
            self.status.setText("Annulé")
            self.right.setText("—")
            self.right.setStyleSheet(f"color: {theme.FAINT};")
        self._update_cancel()

    def _update_cancel(self) -> None:
        active = self.job.status in (QUEUED, RUNNING)
        self.cancel_btn.setVisible(active and self._hover)
        self.right.setVisible(not (active and self._hover))

    def enterEvent(self, e) -> None:
        self._hover = True
        self._update_cancel()
        self.update()

    def leaveEvent(self, e) -> None:
        self._hover = False
        self._update_cancel()
        self.update()

    def mouseReleaseEvent(self, e) -> None:
        if e.button() == Qt.LeftButton and self.job.status == DONE and self.job.outputs:
            reveal(self.job.outputs[0])

    def paintEvent(self, e) -> None:
        if self._hover:
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 9))
            p.drawRoundedRect(self.rect().adjusted(2, 1, -2, -1), 10, 10)


class ProgressWindow(QWidget):
    MARGIN = 18  # place pour l'ombre

    def __init__(self, manager: JobManager):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.manager = manager
        self.rows: dict[int, JobRow] = {}
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setWindowTitle(APP_NAME)
        self._drag: QPoint | None = None
        self._user_moved = False

        self.card = QFrame(self)
        self.card.setObjectName("Card")
        self.card.setStyleSheet(f"QFrame#Card {{ background: {theme.CARD}; border: 1px solid {theme.BORDER};"
                                f" border-radius: 16px; }}")
        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(36)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 150))
        self.card.setGraphicsEffect(shadow)

        # En-tête
        logo = QLabel()
        logo.setPixmap(app_pixmap(30))
        logo.setFixedSize(30, 30)
        title = QLabel(APP_NAME)
        title.setFont(theme.font(11, QFont.DemiBold))
        self.subtitle = QLabel("Préparation…")
        self.subtitle.setFont(theme.font(8.5))
        self.subtitle.setProperty("muted", True)
        tcol = QVBoxLayout()
        tcol.setSpacing(0)
        tcol.addWidget(title)
        tcol.addWidget(self.subtitle)
        self.counter = QLabel("")
        self.counter.setFont(theme.font(9, QFont.DemiBold))
        self.counter.setProperty("muted", True)
        close = QPushButton("✕")
        close.setProperty("flat", True)
        close.setFixedSize(28, 28)
        close.setCursor(Qt.PointingHandCursor)
        close.setToolTip("Fermer (annule ce qui reste)")
        close.clicked.connect(self.request_close)
        head = QHBoxLayout()
        head.setSpacing(10)
        head.addWidget(logo)
        head.addLayout(tcol, 1)
        head.addWidget(self.counter)
        head.addWidget(close)

        self.total = ThinProgress(3)

        # Liste
        self.list_host = QWidget()
        self.list_lay = QVBoxLayout(self.list_host)
        self.list_lay.setContentsMargins(0, 0, 0, 0)
        self.list_lay.setSpacing(2)
        self.list_lay.addStretch(1)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.list_host)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setFrameShape(QFrame.NoFrame)

        # Pied
        self.open_btn = QPushButton("Ouvrir le dossier")
        self.open_btn.setCursor(Qt.PointingHandCursor)
        self.open_btn.clicked.connect(self.open_folder)
        self.open_btn.setEnabled(False)
        self.action_btn = QPushButton("Tout annuler")
        self.action_btn.setCursor(Qt.PointingHandCursor)
        self.action_btn.setProperty("danger", True)
        self.action_btn.clicked.connect(self._action)
        self.countdown = QLabel("")
        self.countdown.setFont(theme.font(8))
        self.countdown.setProperty("faint", True)
        foot = QHBoxLayout()
        foot.setSpacing(8)
        foot.addWidget(self.open_btn)
        foot.addStretch(1)
        foot.addWidget(self.countdown)
        foot.addWidget(self.action_btn)

        inner = QVBoxLayout(self.card)
        inner.setContentsMargins(16, 14, 14, 14)
        inner.setSpacing(10)
        inner.addLayout(head)
        inner.addWidget(self.total)
        inner.addWidget(self.scroll)
        inner.addLayout(foot)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(self.MARGIN, self.MARGIN, self.MARGIN, self.MARGIN)
        outer.addWidget(self.card)

        self.setFixedWidth(WIDTH + 2 * self.MARGIN)

        manager.added.connect(self._on_added)
        manager.changed.connect(self._on_changed)

        self._close_timer = QTimer(self, interval=250)
        self._close_timer.timeout.connect(self._tick_close)
        self._close_left = 0.0
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(260)
        self._fade.setEasingCurve(QEasingCurve.InCubic)
        self._fade.finished.connect(self._fade_done)
        self._fading = False
        self._relayout()

    # --- Positionnement -------------------------------------------------------------

    def _relayout(self) -> None:
        n = max(1, min(MAX_ROWS, len(self.rows)))
        self.scroll.setFixedHeight(n * (ROW_H + 2))
        self.adjustSize()
        if not self._user_moved:
            self._anchor()

    def _anchor(self) -> None:
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        g = screen.availableGeometry()
        self.move(g.right() - self.width() + self.MARGIN - 14, g.bottom() - self.height() + self.MARGIN - 14)

    def sizeHint(self) -> QSize:
        return QSize(WIDTH + 2 * self.MARGIN, super().sizeHint().height())

    # --- Mises à jour ----------------------------------------------------------------

    def _on_added(self, job: Job) -> None:
        row = JobRow(job, self.manager)
        self.rows[job.id] = row
        self.list_lay.insertWidget(self.list_lay.count() - 1, row)
        self._cancel_autoclose()
        self._relayout()
        self._update_summary()
        if not self.isVisible():
            self.show()

    def _on_changed(self, job: Job) -> None:
        row = self.rows.get(job.id)
        if row:
            row.refresh()
            if job.status == RUNNING and job.progress == 0:
                self.scroll.ensureWidgetVisible(row)
        self._update_summary()

    def _update_summary(self) -> None:
        done, failed, total = self.manager.counts()
        busy = self.manager.busy()
        jobs = self.manager.jobs
        overall = sum(j.progress if j.status in (RUNNING, DONE) else (1.0 if j.status in (FAILED, CANCELLED) else 0.0)
                      for j in jobs) / max(1, len(jobs))
        self.total.animate_to(overall)
        self.counter.setText(f"{done + failed}/{total}" if total > 1 else "")
        self.open_btn.setEnabled(any(j.status == DONE and j.outputs for j in jobs))
        if busy:
            running = sum(1 for j in jobs if j.status == RUNNING)
            self.subtitle.setText("Conversion en cours…" if running else "En attente…")
            self.action_btn.setText("Tout annuler")
            self.action_btn.setProperty("danger", True)
            self.total.set_color(None)
        else:
            if failed == 0:
                self.subtitle.setText("Terminé ✓" if total == 1 else f"{done} fichiers convertis ✓")
                self.total.set_color(theme.OK)
            elif done == 0:
                self.subtitle.setText("Échec de la conversion" if total == 1 else "Aucun fichier converti")
                self.total.set_color(theme.ERR)
            else:
                self.subtitle.setText(f"{done} réussi(s), {failed} échec(s)")
                self.total.set_color("#FFB86B")
            self.action_btn.setText("Fermer")
            self.action_btn.setProperty("danger", False)
            self._on_all_done(failed)
        self.action_btn.style().unpolish(self.action_btn)
        self.action_btn.style().polish(self.action_btn)

    def _on_all_done(self, failed: int) -> None:
        if self.manager.settings.open_folder_when_done and not getattr(self, "_opened", False):
            self._opened = True
            self.open_folder()
        if failed == 0 and self.manager.settings.auto_close and not self._close_timer.isActive():
            self._close_left = 3.5
            self._close_timer.start()
            self._tick_close()

    # --- Fermeture auto -------------------------------------------------------------

    def _tick_close(self) -> None:
        if self.underMouse():
            self.countdown.setText("")
            self._close_left = max(self._close_left, 2.0)
            return
        self._close_left -= 0.25
        self.countdown.setText(f"fermeture dans {max(0, int(self._close_left + 0.99))} s")
        if self._close_left <= 0:
            self._close_timer.stop()
            self._fade_out()

    def _cancel_autoclose(self) -> None:
        self._close_timer.stop()
        self.countdown.setText("")
        if self._fading:
            self._fade.stop()
            self._fading = False
            self.setWindowOpacity(1.0)

    def _fade_out(self) -> None:
        self._fading = True
        self._fade.setStartValue(1.0)
        self._fade.setEndValue(0.0)
        self._fade.start()

    def _fade_done(self) -> None:
        if self._fading and not self.manager.busy():
            self.close()

    # --- Actions ---------------------------------------------------------------------

    def _action(self) -> None:
        if self.manager.busy():
            self.manager.cancel_all()
        else:
            self.close()

    def request_close(self) -> None:
        self.manager.cancel_all()
        self.close()

    def open_folder(self) -> None:
        for j in reversed(self.manager.jobs):
            if j.status == DONE and j.outputs:
                reveal(j.outputs[0])
                return

    def closeEvent(self, e) -> None:
        self.manager.cancel_all()
        super().closeEvent(e)
        QApplication.quit()  # fenêtre « outil » : Qt ne quitte pas tout seul

    # --- Déplacement à la souris -----------------------------------------------------

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e) -> None:
        if self._drag is not None and e.buttons() & Qt.LeftButton:
            self.move(e.globalPos() - self._drag)
            self._user_moved = True

    def mouseReleaseEvent(self, e) -> None:
        self._drag = None
